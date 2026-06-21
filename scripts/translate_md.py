"""
translate_md.py — Markdown(+LaTeX) を数式を保持したまま日本語に翻訳する。

marker などで PDF→Markdown 変換した結果を入力とし、本文段落だけを
既存の ChatGPTTranslator で和訳する。数式($...$ / $$...$$)・コードブロック・
画像・表の区切りはプレースホルダに退避してから翻訳し、後で復元する。

使い方:
    python3 scripts/translate_md.py --in Papers/bab/extracted_md/bab.md \
                                    --out Papers/bab/translated_md/01.md

前提: chatgpt_translator.py と同じく、デバッグポート付き Chrome + ChatGPT ログイン。
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from chatgpt_translator import ChatGPTTranslator

# 翻訳対象から退避するパターン（数式・コード・画像）
_PROTECT = [
    (re.compile(r"\$\$.*?\$\$", re.DOTALL)),   # display math
    (re.compile(r"\$[^$\n]+?\$")),             # inline math
    (re.compile(r"```.*?```", re.DOTALL)),     # code fence
    (re.compile(r"`[^`\n]+?`")),               # inline code
    (re.compile(r"!\[[^\]]*\]\([^)]*\)")),     # image
]

BATCH_SIZE = 30
BATCH_SLEEP = 3


def _protect(text: str):
    """数式・コード等をプレースホルダに退避。(置換後テキスト, 復元マップ) を返す。"""
    store = {}
    n = 0
    for pat in _PROTECT:
        def repl(m, ):
            nonlocal n
            key = f"【M{n}】"   # 全角括弧で翻訳エンジンが壊しにくい
            store[key] = m.group(0)
            n += 1
            return key
        text = pat.sub(repl, text)
    return text, store


def _restore(text: str, store: dict) -> str:
    for key, val in store.items():
        text = text.replace(key, val)
    return text


def _translatable_blocks(md: str):
    """段落単位で分割。見出し記号や箇条書き記号は残しつつ本文だけ訳す対象を返す。
    返り値: [(原文ブロック, 翻訳すべきか)]"""
    blocks = re.split(r"\n\s*\n", md)
    result = []
    for b in blocks:
        s = b.strip()
        # 数式のみ・画像のみ・表の罫線のみ・短すぎるものは翻訳しない
        if not s or len(s) < 4:
            result.append((b, False))
            continue
        if re.fullmatch(r"(\$\$.*?\$\$|\!\[.*?\]\(.*?\)|```.*?```)", s, re.DOTALL):
            result.append((b, False))
            continue
        result.append((b, True))
    return result


def _parse_numbered(resp: str, n: int):
    resp = re.sub(r"```[^\n]*\n?", "", resp).strip()
    res = {}
    for line in resp.splitlines():
        m = re.match(r"^\[(\d+)\]\s*(.*)", line.strip())
        if m:
            res[int(m.group(1))] = m.group(2)
    if len(res) == n and all(i + 1 in res for i in range(n)):
        return [res[i + 1] for i in range(n)]
    return None


def translate_markdown(md: str, tr: ChatGPTTranslator) -> str:
    blocks = _translatable_blocks(md)
    # 翻訳対象だけ抜き出し、数式を退避
    targets = [(i, b) for i, (b, do) in enumerate(blocks) if do]
    out = [b for b, _ in blocks]

    protected = []
    stores = []
    for _, b in targets:
        p, s = _protect(b)
        protected.append(p)
        stores.append(s)

    for start in range(0, len(targets), BATCH_SIZE):
        chunk = protected[start:start + BATCH_SIZE]
        payload = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(chunk))
        print(f"  batch {start//BATCH_SIZE+1}: {len(chunk)} blocks")
        ja = None
        for _ in range(3):
            try:
                resp = tr.translate(payload)
                ja = _parse_numbered(resp, len(chunk))
                if ja:
                    break
            except Exception as e:
                print("   retry:", e)
                time.sleep(5)
        if not ja:
            print("   ! batch failed, keeping original")
            ja = chunk
        for k, t in enumerate(ja):
            gi = targets[start + k][0]
            out[gi] = _restore(t, stores[start + k])
        time.sleep(BATCH_SLEEP)

    return "\n\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, type=Path)
    ap.add_argument("--out", dest="out", required=True, type=Path)
    args = ap.parse_args()

    md = args.inp.read_text(encoding="utf-8")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with ChatGPTTranslator(reset_every=15) as tr:
        ja = translate_markdown(md, tr)

    args.out.write_text(ja, encoding="utf-8")
    print(f"Done → {args.out}")


if __name__ == "__main__":
    main()
