"""
embed_images.py — Download CFA lesson images and embed as base64 in raw HTML files.

Reads all raw HTML files, fetches authenticated image URLs via Playwright,
and rewrites img src attributes as data URIs (inline base64).

Usage:
    python3 scripts/embed_images.py            # all files
    python3 scripts/embed_images.py --dry-run  # show stats only

Prerequisite:
    CFA_USER and CFA_PASS set in .env
"""

import re
import base64
import argparse
import time
from pathlib import Path
from collections import defaultdict

from playwright.sync_api import sync_playwright

env_path = Path(__file__).parent.parent / ".env"
env_vars = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip()

CFA_USER = env_vars["CFA_USER"]
CFA_PASS = env_vars["CFA_PASS"]

ROOT_DIR       = Path(__file__).parent.parent
RAW_DIR        = ROOT_DIR / "CFA" / "LV1" / "raw_html"
TRANSLATED_DIR = ROOT_DIR / "CFA" / "LV1" / "translated_html"

IMG_PATTERN = re.compile(
    r'https://learn\.cfainstitute\.org/courses/\d+/files/\d+/preview'
)


def collect_urls(dirs=None) -> dict:
    """Return {url: [html_path, ...]} for all image URLs in the given directories."""
    if dirs is None:
        dirs = [RAW_DIR, TRANSLATED_DIR]
    url_to_files = defaultdict(list)
    for d in dirs:
        for html_path in sorted(Path(d).glob("courses_*.html")):
            text = html_path.read_text(encoding="utf-8", errors="ignore")
            for url in set(IMG_PATTERN.findall(text)):
                url_to_files[url].append(html_path)
    return url_to_files


def login(page):
    """Log in to CFA Institute learning platform."""
    start_url = "https://learn.cfainstitute.org/courses/1864/pages"
    page.goto(start_url, timeout=30000)
    page.wait_for_timeout(3000)

    email_sel = (
        "input#email_withoutPattern, "
        "input[name='Email Address'], "
        "input[placeholder='Email Address'], "
        "input[type='email']"
    )
    page.wait_for_selector(email_sel, timeout=15000)
    page.fill(email_sel, CFA_USER)
    page.click("#next")
    page.wait_for_timeout(3000)

    page.fill("input[type='password']", CFA_PASS)
    page.click("button[type='submit']")
    page.wait_for_timeout(5000)
    print(f"  Logged in. Current URL: {page.url}")


def fetch_image(page, url: str):
    """Fetch image bytes via authenticated browser request. Returns (mime, bytes) or None."""
    try:
        resp = page.request.get(url, timeout=15000)
        if resp.status != 200:
            print(f"  [HTTP {resp.status}] {url}")
            return None
        mime = resp.headers.get("content-type", "image/png").split(";")[0].strip()
        return mime, resp.body()
    except Exception as e:
        print(f"  [error] {url}: {e}")
        return None


def to_data_uri(mime: str, data: bytes) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def embed_into_files(html_paths, url: str, data_uri: str):
    """Replace all occurrences of url with data_uri in the given HTML files."""
    for path in html_paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if url in text:
            path.write_text(text.replace(url, data_uri), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Show stats without downloading or modifying files")
    ap.add_argument("--translated-only", action="store_true",
                    help="Only process translated_html/ (skip raw_html/)")
    ap.add_argument("--dirs", nargs="+", metavar="DIR",
                    help="Explicit directories to process (overrides defaults)")
    args = ap.parse_args()

    if args.dirs:
        dirs = [ROOT_DIR / d for d in args.dirs]
    elif args.translated_only:
        dirs = [TRANSLATED_DIR]
    else:
        dirs = None
    url_to_files = collect_urls(dirs)
    total_urls = len(url_to_files)
    total_refs = sum(len(v) for v in url_to_files.values())
    print(f"{total_urls} unique image URLs across {total_refs} file references")

    if args.dry_run:
        return

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("Logging in...")
        login(page)

        ok = 0
        fail = 0
        for i, (url, paths) in enumerate(url_to_files.items(), 1):
            print(f"[{i}/{total_urls}] {url.split('/')[-2]}", end="  ")
            result = fetch_image(page, url)
            if result:
                mime, data = result
                data_uri = to_data_uri(mime, data)
                embed_into_files(paths, url, data_uri)
                print(f"{len(data)//1024}KB → {len(paths)} file(s)")
                ok += 1
            else:
                fail += 1
            time.sleep(0.3)

        browser.close()

    print(f"\nDone. {ok} embedded, {fail} failed.")


if __name__ == "__main__":
    main()
