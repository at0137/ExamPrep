"""
ステップ1：Chromeを全部閉じてから↓を実行
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
ステップ2： 開いたChromeでChatGPTにログイン（普通に）                                                                                                                                          
ステップ3： サンプル翻訳を実行
python3 scripts/translate_glossary.py --sample

スクリプトは自動でポート9222のChromeに接続するので、CAPTCHAは出ません。ログイン済みの本物のブラウザセッションをそのまま使うためです。                                                          
---

chatgpt_translator.py — General-purpose ChatGPT browser translation engine.

Usage as a module:
    from chatgpt_translator import ChatGPTTranslator

    with ChatGPTTranslator() as t:
        result = t.translate("The quick brown fox jumps over the lazy dog.")

Usage as a CLI (test):
    python3 chatgpt_translator.py "Hello, world."
"""

import re
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

SESSION_DIR = Path.home() / ".chatgpt_session"

# Prompt format from INSTRUCTION.txt
_PROMPT_TEMPLATE = """\
CFAの学習をしており、教材の和訳を依頼したい. メジャーでない固有名詞の英単語の場合は、()で右に英語を付記しておいてくれると試験本番のときに助かる. 和訳のレスポンスは原文の翻訳のみとすること.
===
{text}"""


class ChatGPTTranslator:
    """
    Automates ChatGPT in a browser to translate text.

    Use as a context manager:
        with ChatGPTTranslator() as t:
            ja = t.translate("some English text")

    Or manage lifecycle manually:
        t = ChatGPTTranslator()
        t.start()
        ja = t.translate("...")
        t.stop()
    """

    def __init__(self, headless: bool = False, reset_every: int = 10,
                 cdp_url: str = "http://127.0.0.1:9222"):
        """
        Args:
            headless:     Run browser invisibly. Ignored when using CDP mode.
            reset_every:  Start a new chat every N translate() calls.
            cdp_url:      Chrome DevTools Protocol URL for existing Chrome.
                          Set to None to use Playwright's own browser.
        """
        self.headless    = headless
        self.reset_every = reset_every
        self.cdp_url     = cdp_url
        self._pw         = None
        self._browser    = None
        self._page       = None
        self._call_count = 0
        self._cdp_mode   = False

    # ── lifecycle ────────────────────────────────────────────────────

    def start(self):
        """Connect to existing Chrome (CDP) or launch a new browser."""
        self._pw = sync_playwright().start()

        if self.cdp_url:
            # Connect to user's already-running Chrome — no bot detection
            try:
                self._browser  = self._pw.chromium.connect_over_cdp(self.cdp_url)
                self._cdp_mode = True
                # Use the first existing page that has ChatGPT open, or open new one
                contexts = self._browser.contexts
                self._page = None
                for ctx in contexts:
                    for pg in ctx.pages:
                        if "chat.openai.com" in pg.url or "chatgpt.com" in pg.url:
                            self._page = pg
                            break
                    if self._page:
                        break
                if not self._page:
                    ctx = contexts[0] if contexts else self._browser.new_context()
                    self._page = ctx.new_page()
                    self._page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=30000)
                print(f"既存のChromeに接続しました。 ({self._page.url[:60]})")
            except Exception as e:
                print(f"CDP接続失敗: {e}")
                print()
                print("─" * 60)
                print("Chromeがデバッグモードで起動していません。")
                print("以下のコマンドでChromeを起動してからもう一度実行してください：")
                print()
                print("  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
                print()
                print("起動後、ChatGPTにログインしてからスクリプトを再実行してください。")
                print("─" * 60)
                raise SystemExit(1)
        else:
            self._start_own_browser()

        self._new_chat()

    def _start_own_browser(self):
        """Launch Playwright's built-in Chromium with saved session."""
        SESSION_DIR.mkdir(exist_ok=True)
        # Use built-in Chromium (not system Chrome) to avoid conflicts
        # when Chrome is already running
        self._ctx = self._pw.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=self.headless,
        )
        self._browser = self._ctx  # persistent_context acts as both browser+context
        # Re-use existing page if available, otherwise open new one
        pages = self._ctx.pages
        self._page = pages[0] if pages else self._ctx.new_page()
        self._page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=30000)
        self._page.wait_for_timeout(2000)
        if "login" in self._page.url or "auth" in self._page.url:
            print("ChatGPTにログインしてください。完了後Enterを押してください。")
            input()
            self._page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=30000)

    def stop(self):
        """Disconnect from browser and stop playwright."""
        if self._browser:
            if self._cdp_mode:
                self._browser.close()  # just disconnects, doesn't kill Chrome
            else:
                self._browser.close()
        if self._pw:
            self._pw.stop()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ── public API ───────────────────────────────────────────────────

    def translate(self, text: str) -> str:
        """
        Translate English text to Japanese via ChatGPT.

        Args:
            text: English text to translate. Can be multi-line.

        Returns:
            Japanese translation (translation only, no extra commentary).
        """
        if self._page is None:
            raise RuntimeError("Call start() or use as context manager first.")

        # Periodic chat reset to avoid context bloat
        self._call_count += 1
        if self._call_count > 1 and self._call_count % self.reset_every == 1:
            print("  (新しいチャットを開始...)")
            self._new_chat()

        prompt = _PROMPT_TEMPLATE.format(text=text)
        self._send(prompt)
        self._wait_for_completion()
        return self._last_response()

    @staticmethod
    def login():
        """Open browser for one-time manual login, then save session."""
        print("ブラウザを開きます。ChatGPTにログインしてください。")
        SESSION_DIR.mkdir(exist_ok=True)
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(SESSION_DIR), headless=False, channel="chrome"
            )
            page = ctx.new_page()
            page.goto("https://chatgpt.com/")
            input("ログイン完了後Enterを押してください...")
            ctx.close()
        print("セッションを保存しました。")

    # ── private helpers ──────────────────────────────────────────────

    def _new_chat(self):
        self._page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=30000)
        self._page.wait_for_timeout(2000)

    def _send(self, text: str):
        box = self._page.locator(
            '#prompt-textarea, [data-testid="prompt-textarea"]'
        ).first
        box.click()
        box.fill(text)
        self._page.wait_for_timeout(400)
        self._page.locator(
            '[data-testid="send-button"], button[aria-label="Send message"]'
        ).first.click()

    def _wait_for_completion(self):
        self._page.wait_for_timeout(2000)
        try:
            self._page.wait_for_selector(
                '[data-testid="stop-button"], button[aria-label="Stop generating"]',
                state="detached", timeout=120000,
            )
        except PWTimeout:
            pass
        self._page.wait_for_timeout(800)

    def _last_response(self) -> str:
        msgs = self._page.query_selector_all('[data-message-author-role="assistant"]')
        if not msgs:
            msgs = self._page.query_selector_all('.markdown')
        if not msgs:
            return ""
        return msgs[-1].inner_text().strip()


# ── CLI test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 chatgpt_translator.py <english text>")
        print("       python3 chatgpt_translator.py --login")
        sys.exit(1)

    if sys.argv[1] == "--login":
        ChatGPTTranslator.login()
    else:
        text = " ".join(sys.argv[1:])
        with ChatGPTTranslator() as t:
            result = t.translate(text)
            print(result)
