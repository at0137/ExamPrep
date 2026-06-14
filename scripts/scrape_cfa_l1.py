"""
scrape_cfa_l1.py — Scrape CFA L1 learning materials from CFA Institute website.
Saves HTML content to CFA/LV1/raw_html/ directory.

Module index URLs are read from CFA/LV1/INDEX.md.

Usage:
    python3 scripts/scrape_cfa_l1.py
    python3 scripts/scrape_cfa_l1.py --resume   # skip already-saved files
"""

import re
import time
import argparse
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Load credentials from .env
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

INDEX_MD   = Path(__file__).parent.parent / "CFA" / "LV1" / "INDEX.md"
OUTPUT_DIR = Path(__file__).parent.parent / "CFA" / "LV1" / "raw_html"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_module_urls() -> list:
    """Read course module index URLs from INDEX.md."""
    urls = []
    for line in INDEX_MD.read_text().splitlines():
        line = line.strip()
        if line.startswith("http"):
            # Normalize double-slash in path
            url = re.sub(r"(?<!:)//+", "/", line)
            urls.append(url)
    return urls


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    return text.strip("_")[:80]


def save_page(page, url: str, filename: str) -> bool:
    """Navigate to URL, wait for content, save HTML. Returns True on success."""
    output_path = OUTPUT_DIR / filename
    if output_path.exists():
        print(f"  [skip] {filename}")
        return True

    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        html = page.content()
        output_path.write_text(html, encoding="utf-8")
        print(f"  [saved] {filename} ({len(html):,} chars)")
        return True
    except PlaywrightTimeoutError:
        print(f"  [timeout] {url} — saving partial")
        try:
            html = page.content()
            output_path.write_text(html, encoding="utf-8")
        except Exception:
            pass
        return False
    except Exception as e:
        print(f"  [error] {url}: {e}")
        return False


def login(page):
    """Log in to CFA Institute learning platform via Azure B2C SSO."""
    # Use first course URL to trigger SSO redirect
    module_urls = load_module_urls()
    print(f"Navigating to trigger SSO login...")
    page.goto(module_urls[0], timeout=30000)
    page.wait_for_timeout(3000)
    print(f"  Redirected to: {page.url}")

    # Save debug snapshot
    (OUTPUT_DIR / "_debug_login.html").write_text(page.content(), encoding="utf-8")

    try:
        # Fill email (Azure B2C step 1)
        email_sel = (
            "input#email_withoutPattern, "
            "input[name='Email Address'], "
            "input[placeholder='Email Address'], "
            "input[type='email']"
        )
        page.wait_for_selector(email_sel, timeout=15000)
        page.fill(email_sel, CFA_USER)
        print("  Filled email")

        page.click("#next")
        print("  Clicked Continue")
        page.wait_for_timeout(3000)

        # Fill password (Azure B2C step 2)
        page.wait_for_selector("input[type='password']", timeout=15000)
        page.fill("input[type='password']", CFA_PASS)
        print("  Filled password")

        page.click("#next, button[type='submit'], input[type='submit']")
        print("  Submitted")

        page.wait_for_url("**/learn.cfainstitute.org/**", timeout=45000)
        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        print(f"  Logged in. URL: {page.url}")
    except Exception as e:
        print(f"  Login error: {e}  (URL: {page.url})")
        (OUTPUT_DIR / "_debug_after_login.html").write_text(page.content(), encoding="utf-8")


def get_lesson_urls(page, module_url: str) -> list:
    """Return list of (url, title) for all lessons in a course module index."""
    course_id = re.search(r"/courses/(\d+)/", module_url).group(1)

    page.goto(module_url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    # Save the module index page
    save_page(page, module_url, f"course_{course_id}_modules.html")

    links = page.evaluate("""() => {
        const anchors = Array.from(document.querySelectorAll('a[href]'));
        return anchors
            .map(a => ({href: a.href, text: a.textContent.trim()}))
            .filter(l =>
                l.href.includes('/courses/') &&
                l.href.includes('/modules/items/') &&
                !l.href.includes('{{')
            );
    }""")

    seen = set()
    result = []
    for link in links:
        href = link["href"]
        if href not in seen:
            seen.add(href)
            result.append((href, link["text"]))

    print(f"  Found {len(result)} lessons in course {course_id}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true", help="Skip already-saved files")
    args = ap.parse_args()

    module_urls = load_module_urls()
    print(f"Loaded {len(module_urls)} course URLs from INDEX.md")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        # Login
        login(page)

        if "learn.cfainstitute.org" not in page.url:
            print("Login failed — check _debug_after_login.html")
            browser.close()
            return

        # Collect all lesson URLs across all courses
        all_lessons = []
        for module_url in module_urls:
            course_id = re.search(r"/courses/(\d+)/", module_url).group(1)
            print(f"\nCourse {course_id}: {module_url}")
            lessons = get_lesson_urls(page, module_url)
            all_lessons.extend(lessons)

        print(f"\nTotal lessons: {len(all_lessons)}")

        # Scrape each lesson
        errors = 0
        for i, (url, title) in enumerate(all_lessons, 1):
            parsed   = urlparse(url)
            path_slug = parsed.path.strip("/").replace("/", "_")
            title_slug = slugify(title) if title else "untitled"
            filename = f"{path_slug}_{title_slug}.html"
            filename = re.sub(r"_+", "_", filename)

            print(f"\n[{i}/{len(all_lessons)}] {title[:70] if title else url}")
            ok = save_page(page, url, filename)
            if not ok:
                errors += 1
            time.sleep(0.5)

        browser.close()
        print(f"\nDone. Saved to: {OUTPUT_DIR}")
        print(f"Errors: {errors}/{len(all_lessons)}")


if __name__ == "__main__":
    main()
