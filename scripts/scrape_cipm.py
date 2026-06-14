"""
Scrape CIPM learning materials from CFA Institute website.
Saves HTML content to CIPM/raw/ directory.
"""

import os
import re
import time
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

OUTPUT_DIR = Path(__file__).parent.parent / "CIPM" / "LV1" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODULE_URLS = [
    "https://learn.cfainstitute.org/courses/1370/modules",
    "https://learn.cfainstitute.org/courses/1366/modules",
    "https://learn.cfainstitute.org/courses/1369/modules",
    "https://learn.cfainstitute.org/courses/1367/modules",
    "https://learn.cfainstitute.org/courses/1368/modules",
]

LOGIN_URL = "https://www.cfainstitute.org/en/membership/login"
SSO_PATTERN = re.compile(r"sso|login|signin|auth", re.IGNORECASE)


def slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    return text.strip("_")[:80]


def save_page(page, url: str, filename: str):
    """Navigate to URL and save full HTML content."""
    output_path = OUTPUT_DIR / filename
    if output_path.exists():
        print(f"  [skip] already saved: {filename}")
        return

    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        # Wait for main content to load
        page.wait_for_timeout(2000)
        html = page.content()
        output_path.write_text(html, encoding="utf-8")
        print(f"  [saved] {filename} ({len(html):,} chars)")
    except PlaywrightTimeoutError:
        print(f"  [timeout] {url}")
        # Try to save whatever is loaded
        try:
            html = page.content()
            output_path.write_text(html, encoding="utf-8")
            print(f"  [partial] {filename}")
        except Exception as e:
            print(f"  [error] could not save {filename}: {e}")
    except Exception as e:
        print(f"  [error] {url}: {e}")


def login(page):
    """Log in to CFA Institute learning platform via Azure B2C SSO."""
    print("Navigating to course page (triggers SSO redirect)...")
    # Going to the course directly triggers SSO redirect
    page.goto(MODULE_URLS[0], timeout=30000)
    page.wait_for_timeout(3000)
    print(f"  Redirected to: {page.url}")

    # Save debug
    (OUTPUT_DIR / "_debug_login.html").write_text(page.content(), encoding="utf-8")

    try:
        # Fill email field (Azure B2C)
        email_selector = (
            "input#email_withoutPattern, "
            "input[name='Email Address'], "
            "input[placeholder='Email Address'], "
            "input[type='email']"
        )
        page.wait_for_selector(email_selector, timeout=15000)
        page.fill(email_selector, CFA_USER)
        print("  Filled email")

        # Click Continue button
        page.click("#next")
        print("  Clicked Continue")
        page.wait_for_timeout(3000)

        # Check if password is now visible on same page or new page
        (OUTPUT_DIR / "_debug_after_email.html").write_text(page.content(), encoding="utf-8")
        print(f"  URL after Continue: {page.url}")

        # Fill password
        page.wait_for_selector("input[type='password']", timeout=15000)
        page.fill("input[type='password']", CFA_PASS)
        print("  Filled password")

        # Click sign in / submit button
        page.click("#next, button[type='submit'], input[type='submit']")
        print("  Submitted login form")
        # Wait for full OAuth redirect chain to complete
        page.wait_for_url("**/learn.cfainstitute.org/**", timeout=45000)
        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        print(f"  Current URL after login: {page.url}")
    except Exception as e:
        print(f"  Login error: {e}")
        print(f"  Current URL: {page.url}")
        (OUTPUT_DIR / "_debug_after_login.html").write_text(page.content(), encoding="utf-8")


def get_module_lesson_urls(page, module_url: str):
    """Get all lesson/content URLs from a module index page."""
    page.goto(module_url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    # Save module index page
    course_id = re.search(r"/courses/(\d+)/", module_url).group(1)
    save_page(page, module_url, f"course_{course_id}_modules.html")

    # Find links to lessons/content within this course
    links = page.evaluate("""() => {
        const anchors = Array.from(document.querySelectorAll('a[href]'));
        return anchors.map(a => ({href: a.href, text: a.textContent.trim()}))
                      .filter(l => l.href.includes('/courses/') &&
                                   l.href.includes('/modules/items/') &&
                                   !l.href.includes('{{'));
    }""")

    # Deduplicate
    seen = set()
    result = []
    for link in links:
        href = link["href"]
        if href not in seen:
            seen.add(href)
            result.append((href, link["text"]))

    print(f"  Found {len(result)} lesson links in course {course_id}")
    return result


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Step 1: Log in
        login(page)

        # Verify login by checking current URL
        current_url = page.url
        print(f"\nPost-login URL: {current_url}")

        if "learn.cfainstitute.org" not in current_url:
            print("  WARNING: Not on learn.cfainstitute.org - login may have failed")
            try:
                (OUTPUT_DIR / "_debug_after_login.html").write_text(page.content(), encoding="utf-8")
            except Exception:
                pass
            print("  Debug page saved. Exiting.")
            browser.close()
            return

        # Step 2: Scrape each module
        all_lesson_urls = []
        for module_url in MODULE_URLS:
            print(f"\nProcessing module: {module_url}")
            lessons = get_module_lesson_urls(page, module_url)
            all_lesson_urls.extend(lessons)

        print(f"\nTotal lesson URLs found: {len(all_lesson_urls)}")

        # Step 3: Scrape each lesson
        for i, (url, title) in enumerate(all_lesson_urls, 1):
            # Build filename from URL
            parsed = urlparse(url)
            path_parts = parsed.path.strip("/").replace("/", "_")
            slug = slugify(title) if title else "untitled"
            filename = f"{path_parts}_{slug}.html"
            filename = re.sub(r"_+", "_", filename)

            print(f"\n[{i}/{len(all_lesson_urls)}] {title[:60] if title else url}")
            save_page(page, url, filename)
            time.sleep(0.5)  # polite delay

        browser.close()
        print(f"\nDone. Files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
