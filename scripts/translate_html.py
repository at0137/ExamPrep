"""
translate_html.py — HTML lesson translator (CFA / CIPM)

Reads scraped HTML from an input directory, translates text via ChatGPT,
and writes translated HTML to an output directory.

Math formulas (.cfa-curriculum-display-formula-container) are kept as-is.

Usage:
    python3 scripts/translate_html.py                                         # CFA LV1 (default)
    python3 scripts/translate_html.py --input-dir CIPM/LV1/original --output-dir CIPM/LV1/translated_html
    python3 scripts/translate_html.py --sample 5                              # first N lessons
    python3 scripts/translate_html.py --file <name>                           # single file
    python3 scripts/translate_html.py --resume                                # skip already translated

Prerequisite:
    Chrome running with --remote-debugging-port=9222 and ChatGPT logged in.
"""

import json, re, time, argparse, sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag

sys.path.insert(0, str(Path(__file__).parent))
from chatgpt_translator import ChatGPTTranslator

_REPO_ROOT = Path(__file__).parent.parent
_DEFAULT_INPUT  = _REPO_ROOT / "CFA" / "LV1" / "original"
_DEFAULT_OUTPUT = _REPO_ROOT / "CFA" / "LV1" / "translated_html"

# Set at runtime by main(); module-level names kept for backwards compatibility
RAW_DIR: Path = _DEFAULT_INPUT
OUT_DIR: Path = _DEFAULT_OUTPUT

# Tags whose text content should be translated
TRANSLATE_TAGS = {"p", "h2", "h3", "h4", "li", "td", "th", "caption"}

# Tags/classes to skip entirely (math, decorative, nav)
SKIP_CLASSES = {
    "cfa-curriculum-display-formula-container",
    "MathJax_Preview", "MathJax_SVG", "MathJax",
    "screenreader-only", "dp-icon-content",
}
SKIP_IDS = {"todo-date-mount-point"}

# How many text items to send per ChatGPT request
BATCH_SIZE = 40

# Seconds to wait between batches (be polite to ChatGPT)
BATCH_SLEEP = 3


# ── HTML parsing ─────────────────────────────────────────────────────────────

def _in_formula(tag: Tag) -> bool:
    """True if this tag is inside a math formula container."""
    for parent in tag.parents:
        if not isinstance(parent, Tag):
            continue
        cls = parent.get("class") or []
        if any(c in SKIP_CLASSES for c in cls):
            return True
        if parent.get("id") in SKIP_IDS:
            return True
    return False


def _has_formula_child(tag: Tag) -> bool:
    """True if tag directly contains a formula container."""
    for cls in SKIP_CLASSES:
        if tag.find(class_=cls):
            return True
    return False


def extract_elements(soup: BeautifulSoup) -> list:
    """
    Return list of Tag objects that are candidates for translation.
    Each tag must:
      - be one of TRANSLATE_TAGS
      - not be inside a formula container
      - not directly wrap a formula container
      - have meaningful text (>5 chars)
    """
    content = soup.find(class_="show-content")
    if not content:
        return []

    elements = []
    for tag in content.find_all(TRANSLATE_TAGS):
        if _in_formula(tag):
            continue
        if _has_formula_child(tag):
            continue
        text = tag.get_text(separator=" ", strip=True)
        if len(text) < 6:
            continue
        # Skip if it's just a heading label like "Learning Outcome"
        if text in {"Learning Outcome", "The candidate should be able to:"}:
            continue
        elements.append(tag)

    return elements


# ── Translation ───────────────────────────────────────────────────────────────

def _format_batch(texts: list) -> str:
    """Format numbered list for ChatGPT."""
    return "\n".join(f"[{i+1}] {t}" for i, t in enumerate(texts))


def _parse_response(response: str, n: int):
    """Parse [N] translation lines. Returns list of n strings or None."""
    response = re.sub(r"```[^\n]*\n?", "", response).strip()
    results = {}
    for line in response.splitlines():
        m = re.match(r"^\[(\d+)\]\s*(.*)", line.strip())
        if m:
            idx = int(m.group(1))
            results[idx] = m.group(2).strip()
    if len(results) == n and all(i+1 in results for i in range(n)):
        return [results[i+1] for i in range(n)]
    # Fallback: plain lines
    lines = [l.strip() for l in response.splitlines() if l.strip()]
    if len(lines) == n:
        return lines
    return None


def translate_elements(elements: list, translator: ChatGPTTranslator) -> dict:
    """
    Translate all elements in batches.
    Returns {element_id: translated_text}.
    Uses element id() as key since Tag objects are mutable.
    """
    translations = {}
    indices = list(range(len(elements)))
    total_batches = (len(indices) + BATCH_SIZE - 1) // BATCH_SIZE

    for b in range(0, len(indices), BATCH_SIZE):
        batch_idx = indices[b:b + BATCH_SIZE]
        texts = [elements[i].get_text(separator=" ", strip=True) for i in batch_idx]
        bn = b // BATCH_SIZE + 1
        print(f"    batch {bn}/{total_batches} ({len(texts)} items): {texts[0][:50]}…")

        retries = 0
        while retries < 3:
            try:
                response = translator.translate(_format_batch(texts))
                translated = _parse_response(response, len(texts))
                if translated:
                    for i, ja in zip(batch_idx, translated):
                        translations[id(elements[i])] = ja
                    break
                else:
                    print(f"      ✗ parse failed, retry {retries+1}")
                    print(f"        preview: {response[:120]}")
                    retries += 1
            except Exception as e:
                print(f"      error: {e}, retry {retries+1}")
                retries += 1
                time.sleep(5)
        else:
            print(f"      gave up on batch {bn}")

        time.sleep(BATCH_SLEEP)

    return translations


# ── HTML builder ──────────────────────────────────────────────────────────────

def _apply_translations_to_soup(content_soup, trans_map: dict):
    """
    Replace text of translatable elements in-place with Japanese.
    trans_map: {(english_text, occurrence_index): japanese_text}
    """
    usage = {}
    for tag in content_soup.find_all(TRANSLATE_TAGS):
        if _in_formula(tag) or _has_formula_child(tag):
            continue
        text = tag.get_text(separator=" ", strip=True)
        if len(text) < 6:
            continue
        count = usage.get(text, 0)
        ja = trans_map.get((text, count))
        if ja:
            tag.clear()
            tag.string = ja
            usage[text] = count + 1


def _patch_env_body(soup, trans_map: dict):
    """Replace WIKI_PAGE.body inside the ENV <script> with translated HTML."""
    for script in soup.find_all("script"):
        src = script.string or ""
        if "WIKI_PAGE" not in src or '"body"' not in src:
            continue
        m = re.search(r'"body"\s*:\s*("(?:[^"\\]|\\.)*")', src)
        if not m:
            continue
        try:
            body_html = json.loads(m.group(1))
        except Exception:
            continue
        body_soup = BeautifulSoup(body_html, "html.parser")
        _apply_translations_to_soup(body_soup, trans_map)
        new_body_json = json.dumps(str(body_soup), ensure_ascii=False)
        script.string = src[:m.start(1)] + new_body_json + src[m.end(1):]
        return


def build_bilingual_html(original_html: str, translations: dict,
                          elements: list) -> str:
    """
    Replace English text with Japanese translation.
    Also patches ENV.WIKI_PAGE.body so Canvas re-renders in Japanese.
    """
    # Build lookup: (english_text, occurrence_index) → japanese_text
    trans_map = {}
    seen = {}
    for el in elements:
        if id(el) not in translations:
            continue
        text = el.get_text(separator=" ", strip=True)
        count = seen.get(text, 0)
        trans_map[(text, count)] = translations[id(el)]
        seen[text] = count + 1

    soup = BeautifulSoup(original_html, "html.parser")

    # Replace text in the static show-content div
    content = soup.find(class_="show-content")
    if content:
        _apply_translations_to_soup(content, trans_map)

    # Patch ENV so Canvas's re-render also uses Japanese
    _patch_env_body(soup, trans_map)

    return str(soup)


# ── Per-file processing ───────────────────────────────────────────────────────

def process_file(html_path: Path, translator: ChatGPTTranslator,
                 resume: bool = True) -> bool:
    out_path = OUT_DIR / html_path.name
    if resume and out_path.exists():
        print(f"  [skip] {html_path.name}")
        return True

    original_html = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(original_html, "html.parser")

    elements = extract_elements(soup)
    if not elements:
        print(f"  [no-content] {html_path.name}")
        return True

    print(f"  {html_path.name}  ({len(elements)} elements)")

    translations = translate_elements(elements, translator)

    if not translations:
        print(f"  [skip] {html_path.name}: all batches failed, not saving")
        return False

    bilingual = build_bilingual_html(original_html, translations, elements)
    out_path.write_text(bilingual, encoding="utf-8")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def lesson_files() -> list:
    """All lesson HTML files with actual content, sorted."""
    files = sorted(RAW_DIR.glob("courses_*.html"))
    result = []
    for f in files:
        try:
            text = f.read_text(errors="ignore")
            if "show-content" in text and "dp-wrapper" in text:
                result.append(f)
        except Exception:
            pass
    return result


def main():
    global RAW_DIR, OUT_DIR

    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir",  type=Path, metavar="DIR",
                    default=_DEFAULT_INPUT,
                    help="Directory containing original HTML files "
                         f"(default: {_DEFAULT_INPUT})")
    ap.add_argument("--output-dir", type=Path, metavar="DIR",
                    default=_DEFAULT_OUTPUT,
                    help="Directory to write translated HTML files "
                         f"(default: {_DEFAULT_OUTPUT})")
    ap.add_argument("--sample", type=int, metavar="N",
                    help="Translate first N lesson files only")
    ap.add_argument("--file",   type=str, metavar="NAME",
                    help="Translate a single file (name within input-dir)")
    ap.add_argument("--resume", action="store_true", default=True,
                    help="Skip already-translated files (default: on)")
    ap.add_argument("--no-resume", dest="resume", action="store_false",
                    help="Re-translate already-translated files")
    args = ap.parse_args()

    RAW_DIR = _REPO_ROOT / args.input_dir if not args.input_dir.is_absolute() \
              else args.input_dir
    OUT_DIR = _REPO_ROOT / args.output_dir if not args.output_dir.is_absolute() \
              else args.output_dir
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.file:
        files = [RAW_DIR / args.file]
    else:
        files = lesson_files()
        if args.sample:
            files = files[:args.sample]

    print(f"{len(files)} files to process")

    with ChatGPTTranslator(reset_every=20) as tr:
        for i, f in enumerate(files, 1):
            print(f"\n[{i}/{len(files)}] {f.name}")
            process_file(f, tr, resume=args.resume)

    print(f"\nDone. Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
