#!/usr/bin/env python3
"""
Convert combined module HTML files → GFM Markdown
- Math (MathML) → $...$ / $$...$$ via pandoc
- base64 images → extracted as files in _media/ subdir
- Post-process: remove HTML tag remnants in markdown
"""

import subprocess
import re
import shutil
from pathlib import Path
from bs4 import BeautifulSoup

SRC = Path("/Users/tarai/Research/ExamPrep/CFA/LV1/view_by_module")
OUT = Path("/Users/tarai/Research/ExamPrep/CFA/LV1/view_by_module_md")
OUT.mkdir(parents=True, exist_ok=True)

# ── Pre-process HTML before pandoc ────────────────────────────────────────────

def preprocess_html(html_path: Path, tmp_path: Path) -> None:
    """
    Clean up HTML to improve pandoc conversion quality:
    - Remove formula number spans (noise)
    - Remove hidden screenreader elements
    - Remove viewer-nav, scripts, style tags (already done by combiner,
      but double-check)
    - Remove ::: fenced-div class attrs we don't need
    """
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Remove formula number spans
    for span in soup.find_all("span", class_="cfa-curriculum-display-formula-number"):
        span.decompose()

    # Remove screenreader-only spans
    for el in soup.find_all(class_="screenreader-only"):
        el.decompose()

    # Remove dp-icon-content spans (hidden icon labels)
    for el in soup.find_all(class_="dp-icon-content"):
        el.decompose()

    # Remove popup/popover content (glossary tooltips)
    for el in soup.find_all(class_="dp-popup-content"):
        el.decompose()
    for el in soup.find_all(class_="dp-popover-content"):
        el.decompose()

    # Remove empty i tags (icon elements)
    for el in soup.find_all("i"):
        if not el.get_text(strip=True):
            el.decompose()

    # Remove scripts and styles
    for el in soup.find_all(["script", "style"]):
        el.decompose()

    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(str(soup))


# ── Post-process Markdown ──────────────────────────────────────────────────────

# Patterns to clean in generated markdown
_SPAN_INLINE = re.compile(
    r'<span[^>]*class="cfa-curriculum-display-inline-formula"[^>]*>(.*?)</span>',
    re.DOTALL
)
_SPAN_GENERIC = re.compile(r'<span[^>]*>(.*?)</span>', re.DOTALL)
_DIV_OPEN     = re.compile(r'<div[^>]*>\s*\n?')
_DIV_CLOSE    = re.compile(r'</div>\s*\n?')
_FENCED_DIV   = re.compile(r'^:::.*$', re.MULTILINE)  # ::: {.class} or :::
_EMPTY_LINES  = re.compile(r'\n{3,}')
_HTML_COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)
# img tag → markdown image
_IMG_TAG      = re.compile(
    r'<img\b[^>]*?\bsrc="([^"]*)"[^>]*?\balt="([^"]*)"[^>]*/?>',
    re.DOTALL | re.IGNORECASE
)
_IMG_TAG_NOSRC = re.compile(r'<img\b[^>]*/?>',  re.DOTALL | re.IGNORECASE)
# table noise: strip tr/td/th/colgroup/col attributes but keep tags
_TR_ATTR      = re.compile(r'<tr\b[^>]*>', re.IGNORECASE)
_TD_ATTR      = re.compile(r'<td\b[^>]*>', re.IGNORECASE)
_TH_ATTR      = re.compile(r'<th\b[^>]*>', re.IGNORECASE)
_COLGROUP     = re.compile(r'<colgroup>.*?</colgroup>', re.DOTALL | re.IGNORECASE)
_TABLE_ATTR   = re.compile(r'<table\b[^>]*>', re.IGNORECASE)
# anchor remnants
_ANCHOR_EMPTY = re.compile(r'<a\b[^>]*>\s*</a>', re.IGNORECASE)
_ANCHOR_GLOSS = re.compile(r'<a\b[^>]*class="dp-popover-trigger[^"]*"[^>]*>(.*?)</a>',
                            re.DOTALL | re.IGNORECASE)

def postprocess_md(text: str) -> str:
    # Remove HTML comments
    text = _HTML_COMMENT.sub('', text)

    # Remove formula number spans that pandoc didn't convert
    text = re.sub(r'<span[^>]*cfa-curriculum-display-formula-number[^>]*>.*?</span>', '', text)

    # Unwrap inline formula spans (keep content)
    text = _SPAN_INLINE.sub(r'\1', text)

    # Remove remaining simple spans (keep content), multi-pass for nesting
    for _ in range(4):
        text = _SPAN_GENERIC.sub(r'\1', text)

    # Convert <img src="X" alt="Y"> → ![Y](X)
    text = _IMG_TAG.sub(lambda m: f'![{m.group(2)}]({m.group(1)})', text)
    text = _IMG_TAG_NOSRC.sub('', text)  # img without src

    # Clean up glossary anchor wrappers (keep text only)
    text = _ANCHOR_GLOSS.sub(r'\1', text)
    text = _ANCHOR_EMPTY.sub('', text)

    # Strip attributes from table structural tags
    text = _TR_ATTR.sub('<tr>', text)
    text = _TD_ATTR.sub('<td>', text)
    text = _TH_ATTR.sub('<th>', text)
    text = _TABLE_ATTR.sub('<table>', text)
    text = _COLGROUP.sub('', text)

    # Remove div open/close
    text = _DIV_OPEN.sub('', text)
    text = _DIV_CLOSE.sub('\n', text)

    # Remove pandoc fenced-div markers  ::: {.foo} ... :::
    text = _FENCED_DIV.sub('', text)

    # Remove heading attribute blocks {#id .class}
    text = re.sub(r'(#{1,6}[^\n{]+)\s*\{[^}]+\}', r'\1', text)

    # Clean up excessive blank lines
    text = _EMPTY_LINES.sub('\n\n', text)

    return text.strip() + '\n'


# ── Conversion ────────────────────────────────────────────────────────────────

TMP = OUT / "_tmp"
TMP.mkdir(exist_ok=True)

html_files = sorted(
    p for p in SRC.rglob("*.html")
    if p.name != "index.html"
)

print(f"Found {len(html_files)} HTML files to convert")
errors = []

for html_path in html_files:
    rel = html_path.relative_to(SRC)
    md_path = OUT / rel.parent / (rel.stem + ".md")

    md_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_html = TMP / rel.parent.name / html_path.name
    tmp_html.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Pre-process HTML
    preprocess_html(html_path, tmp_html)

    # Step 2: pandoc conversion (no --extract-media: keep base64 data URIs inline)
    cmd = [
        "pandoc",
        str(tmp_html),
        "-f", "html",
        "-t", "gfm",
        "--wrap=none",
        "--no-highlight",
        "-o", str(md_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ERROR: {rel} → {result.stderr[:200]}")
        errors.append(str(rel))
        continue

    # Step 3: Post-process markdown
    text = md_path.read_text(encoding="utf-8")
    text = postprocess_md(text)
    md_path.write_text(text, encoding="utf-8")

    size_kb = md_path.stat().st_size // 1024
    print(f"  ✓ {rel.parent.name}/{md_path.name}  ({size_kb} KB)")

# Clean up tmp
shutil.rmtree(TMP, ignore_errors=True)

print(f"\nDone. Output: {OUT}")
if errors:
    print(f"Errors ({len(errors)}): {errors}")

# ── Copy index.html as index.md ───────────────────────────────────────────────
idx_src = SRC / "index.html"
if idx_src.exists():
    idx_md = OUT / "index.md"
    cmd = ["pandoc", str(idx_src), "-f", "html", "-t", "gfm", "--wrap=none", "-o", str(idx_md)]
    subprocess.run(cmd, check=True)
    text = postprocess_md(idx_md.read_text(encoding="utf-8"))
    idx_md.write_text(text, encoding="utf-8")
    print("Index written.")
