#!/usr/bin/env python3
"""
Combine per-lesson HTML files into one HTML per module for CFA-LV1.
- Flashcards: show all cards with front+back visible simultaneously
- Knowledge Check: reveal all answers (correct highlighted, explanations shown)
- Remove navigation bars and interactive scripts
"""

import os
import re
from pathlib import Path
from bs4 import BeautifulSoup, Tag

SRC = Path("/Users/tarai/Research/ExamPrep/dist/CFA-LV1")
OUT = Path("/Users/tarai/Research/ExamPrep/dist/CFA-LV1-modules")
OUT.mkdir(exist_ok=True)

# ── Parse index.html to get structure ─────────────────────────────────────────
with open(SRC / "index.html", encoding="utf-8") as f:
    idx = BeautifulSoup(f, "html.parser")

# Build: chapters = [ {title, modules: [ {title, items: [(href, label), ...]} ]} ]
chapters = []
current_chapter = None
current_module = None

body = idx.find("body")
for el in body.children:
    if not isinstance(el, Tag):
        continue
    tag = el.name
    if tag == "h2":
        current_chapter = {"title": el.get_text(strip=True), "modules": []}
        chapters.append(current_chapter)
        current_module = None
    elif tag == "h3":
        if current_chapter is None:
            current_chapter = {"title": "General", "modules": []}
            chapters.append(current_chapter)
        current_module = {"title": el.get_text(strip=True), "items": []}
        current_chapter["modules"].append(current_module)
    elif tag == "ul":
        if current_module is None:
            if current_chapter is None:
                current_chapter = {"title": "General", "modules": []}
                chapters.append(current_chapter)
            current_module = {"title": "General", "items": []}
            current_chapter["modules"].append(current_module)
        for li in el.find_all("li"):
            a = li.find("a")
            if a:
                current_module["items"].append((a["href"], a.get_text(strip=True)))

print(f"Parsed index: {len(chapters)} chapters, "
      f"{sum(len(c['modules']) for c in chapters)} modules, "
      f"{sum(len(m['items']) for c in chapters for m in c['modules'])} items")

# ── Distribute "General" sections into adjacent modules ───────────────────────
import re as _re

def extract_topic(label: str) -> str:
    """
    From labels like "Glossary: Rates and Returns",
    "Flashcards: Rates and Returns", "Learning Outcomes: Rates and Returns"
    extract the topic portion (after the colon). Returns "" otherwise.
    """
    m = _re.match(r"^(?:Glossary|Flashcards|Learning Outcomes|Real-?World Applications)[:\s]+(.+)$",
                  label, _re.IGNORECASE)
    return m.group(1).strip() if m else ""

def topic_matches(topic: str, module_title: str) -> bool:
    """True if topic words substantially overlap with module title."""
    if not topic:
        return False
    t_words = set(_re.sub(r"[^a-z0-9 ]", "", topic.lower()).split())
    m_words = set(_re.sub(r"[^a-z0-9 ]", "", module_title.lower()).split())
    # Remove very common stopwords
    stopwords = {"the", "a", "an", "of", "and", "or", "for", "to", "in",
                 "module", "part", "i", "ii", "iii", "iv", "v"}
    t_words -= stopwords
    m_words -= stopwords
    if not t_words:
        return False
    overlap = t_words & m_words
    return len(overlap) / len(t_words) >= 0.5  # >=50% of topic words in title

for chapter in chapters:
    mods = chapter["modules"]
    i = 0
    while i < len(mods):
        mod = mods[i]
        if mod["title"] != "General":
            i += 1
            continue
        # Found a General section — distribute its items
        non_general = [m for m in mods if m["title"] != "General"]
        remaining = []
        for href, label in mod["items"]:
            topic = extract_topic(label)
            # Try to find a matching non-General module in this chapter
            best = None
            best_score = 0
            for nm in non_general:
                if topic_matches(topic, nm["title"]):
                    # score by overlap size
                    t_words = set(_re.sub(r"[^a-z0-9 ]", "", topic.lower()).split())
                    m_words = set(_re.sub(r"[^a-z0-9 ]", "", nm["title"].lower()).split())
                    stopwords = {"the","a","an","of","and","or","for","to","in",
                                 "module","part","i","ii","iii","iv","v"}
                    overlap = (t_words - stopwords) & (m_words - stopwords)
                    if len(overlap) > best_score:
                        best_score = len(overlap)
                        best = nm
            if best:
                best["items"].append((href, label))
            else:
                remaining.append((href, label))
        # Items that didn't match: give to the previous non-General module
        if remaining:
            prev = None
            for j in range(i - 1, -1, -1):
                if mods[j]["title"] != "General":
                    prev = mods[j]
                    break
            if prev:
                prev["items"].extend(remaining)
            else:
                # No previous module: give to the next one
                for j in range(i + 1, len(mods)):
                    if mods[j]["title"] != "General":
                        mods[j]["items"] = remaining + mods[j]["items"]
                        break
        # Remove the General module
        mods.pop(i)
        # Don't increment i — the next element shifted down

total_modules = sum(len(c['modules']) for c in chapters)
total_items = sum(len(m['items']) for c in chapters for m in c['modules'])
print(f"After General merge: {total_modules} modules, {total_items} items")

# ── Helpers ───────────────────────────────────────────────────────────────────

COMMON_CSS = """
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 15px; line-height: 1.65; color: #222;
  max-width: 860px; margin: 0 auto; padding: 24px 20px 60px;
}
h1 { font-size: 26px; color: #1a3a5c; border-bottom: 3px solid #0770a3; padding-bottom: 10px; }
h2.chapter-title { font-size: 20px; color: #0770a3; margin: 40px 0 4px; }
h2.module-title  { font-size: 18px; color: #1a3a5c; margin: 36px 0 4px;
  border-left: 4px solid #0770a3; padding-left: 10px; }
h3.lesson-title  { font-size: 15px; color: #555; margin: 32px 0 8px;
  border-top: 1px solid #ddd; padding-top: 10px; text-transform: uppercase; letter-spacing: .5px; }
hr.lesson-sep { border: none; border-top: 1px solid #e0e0e0; margin: 28px 0; }

/* Tables */
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 14px; }
th, td { border: 1px solid #ccc; padding: 6px 10px; vertical-align: top; }
th { background: #e8f0f7; font-weight: 600; }

/* Knowledge Check ── fully revealed */
.dp-qc { margin: 16px 0; border: 1px solid #ccc; border-radius: 8px; padding: 14px 16px; background: #fafafa; }
.dp-qc > p, .dp-qc-question { font-weight: 600; margin-bottom: 10px; }
dl.dp-qc-answers { margin: 0; }
dt.dp-qc-answer { padding: 8px 12px; margin: 4px 0; border-radius: 5px;
  border: 1px solid #ddd; background: #fff; list-style: none; }
dt.dp-qc-answer.dp-qc-correct { background: #e8f5e9 !important; border-color: #2e7d32;
  font-weight: 700; }
dt.dp-qc-answer.dp-qc-correct::before { content: "✓ "; color: #2e7d32; }
dt.dp-qc-answer:not(.dp-qc-correct) { color: #555; }
dd.dp-qc-response { display: block !important; padding: 6px 12px; margin: 2px 0 8px 20px;
  background: #f3f8ff; border-left: 3px solid #0770a3; font-size: 13px; }
a.dp-qc-submit, .qc-reset-btn, .qc-result-banner { display: none !important; }

/* Flashcards ── all cards shown, front then back */
.fc-card-static { margin: 10px 0 16px; border-radius: 8px; overflow: hidden;
  border: 1px solid #0770a3; }
.fc-card-static .fc-front { background: #f0f7fc; padding: 14px 18px;
  border-bottom: 1px solid #0770a3; font-weight: 600; }
.fc-card-static .fc-back  { background: #e8f5e9; padding: 14px 18px;
  border-top: 1px solid #2e7d32; }
.fc-card-static .fc-label { font-size: 11px; color: #888; text-transform: uppercase;
  letter-spacing: .5px; margin-bottom: 4px; }

/* Misc content blocks */
.cfa-curriculum-los-box, .cfa-curriculum-overview-box {
  background: #f8f9ff; border: 1px solid #c5d5e8; border-radius: 6px;
  padding: 12px 16px; margin: 12px 0;
}
.cfa-curriculum-example-box { background: #fffbf0; border: 1px solid #e0cc88;
  border-radius: 6px; padding: 12px 16px; margin: 12px 0; }
.dp-qc-answer-letter { font-weight: 700; margin-right: 6px; }

/* Hide things we don't need */
.dp-popup-content, .dp-popover-content, .dp-icon-content,
.screenreader-only, .fc-hint, .fc-nav,
.flashcard-container > .controls,
#viewer-nav { display: none !important; }

/* MathML display */
math { font-size: 1em; }
.cfa-curriculum-display-formula-container { overflow-x: auto; margin: 12px 0; }

/* TOC */
.toc { background: #f5f8ff; border: 1px solid #c0d0e0; border-radius: 8px;
  padding: 16px 20px; margin-bottom: 32px; }
.toc h2 { margin-top: 0; font-size: 15px; }
.toc ol { margin: 0; padding-left: 20px; }
.toc li { margin: 3px 0; font-size: 13px; }
.toc a { color: #0770a3; text-decoration: none; }
.toc a:hover { text-decoration: underline; }
"""


def load_content(href: str):
    """Load a lesson file and return the main content div, or None if missing."""
    path = SRC / href
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    return soup.find("div", class_="show-content")


def transform_flashcards(content: Tag) -> None:
    """Replace carousel flashcards with static card pairs (front + back)."""
    for container in content.find_all("div", class_="flashcard-container"):
        wrapper = container.parent  # dp-wrapper
        cards_data = []
        for card in container.find_all("div", class_="flashcard"):
            front = card.find("div", class_="front")
            back  = card.find("div", class_="back")
            cards_data.append((
                front.decode_contents() if front else "",
                back.decode_contents()  if back  else "",
            ))
        # Build static replacement
        new_html = '<div class="fc-static-list">'
        for i, (f, b) in enumerate(cards_data, 1):
            new_html += (
                f'<div class="fc-card-static">'
                f'<div class="fc-front"><div class="fc-label">表 ({i}/{len(cards_data)})</div>{f}</div>'
                f'<div class="fc-back"><div class="fc-label">裏</div>{b}</div>'
                f'</div>'
            )
        new_html += '</div>'
        new_tag = BeautifulSoup(new_html, "html.parser")
        container.replace_with(new_tag)

    # Also hide the old controls button rows
    for ctrl in content.find_all("div", class_="controls"):
        ctrl.decompose()


def transform_knowledge_checks(content: Tag) -> None:
    """Reveal all Knowledge Check answers (show correct + all explanations)."""
    for qc in content.find_all(class_="dp-qc"):
        # Show all dd.dp-qc-response
        for dd in qc.find_all("dd", class_="dp-qc-response"):
            for cls in ["d-none", "dp-qc-response"]:
                dd["class"] = [c for c in dd.get("class", []) if c != "d-none"]
            dd["class"] = list(set(dd.get("class", [])))
            dd["style"] = "display:block"
        # Submit button → hide
        for btn in qc.find_all("a", class_="dp-qc-submit"):
            btn.decompose()


def clean_content(content: Tag) -> None:
    """Remove nav bars, scripts, interactive elements."""
    for el in content.find_all(id="viewer-nav"):
        el.decompose()
    for el in content.find_all("script"):
        el.decompose()
    for el in content.find_all(class_="fc-hint"):
        el.decompose()
    for el in content.find_all(class_="fc-nav"):
        el.decompose()
    # Remove style tags from individual files (we use our own)
    for el in content.find_all("style"):
        el.decompose()


def build_module_html(chapter_title: str, module_title: str, items) -> str:
    """Build combined HTML for one module."""
    lessons_html_parts = []
    toc_items = []

    for idx_i, (href, label) in enumerate(items):
        content = load_content(href)
        if content is None:
            continue

        anchor = f"lesson-{idx_i}"
        toc_items.append((anchor, label))

        # Transform interactive elements
        transform_flashcards(content)
        transform_knowledge_checks(content)
        clean_content(content)

        lesson_html = (
            f'<hr class="lesson-sep" id="{anchor}">'
            f'<h3 class="lesson-title">{label}</h3>'
            + content.decode_contents()
        )
        lessons_html_parts.append(lesson_html)

    # Table of contents
    toc_html = '<div class="toc"><h2>目次 (Table of Contents)</h2><ol>'
    for anchor, label in toc_items:
        toc_html += f'<li><a href="#{anchor}">{label}</a></li>'
    toc_html += '</ol></div>'

    full_title = f"{chapter_title} — {module_title}"
    body_content = "\n".join(lessons_html_parts)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{full_title}</title>
<style>
{COMMON_CSS}
</style>
</head>
<body>
<h1>{full_title}</h1>
{toc_html}
{body_content}
</body>
</html>"""


# ── Main loop ─────────────────────────────────────────────────────────────────

def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s]+", "_", s.strip())
    return s[:80]


generated = 0
for ch_idx, chapter in enumerate(chapters, 1):
    ch_slug = f"{ch_idx:02d}_{slugify(chapter['title'])}"
    ch_dir = OUT / ch_slug
    ch_dir.mkdir(exist_ok=True)

    for mod_idx, module in enumerate(chapter["modules"], 1):
        if not module["items"]:
            continue
        mod_slug = f"{mod_idx:02d}_{slugify(module['title'])}"
        out_path = ch_dir / f"{mod_slug}.html"

        html = build_module_html(chapter["title"], module["title"], module["items"])
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"  → {out_path.relative_to(OUT)}  ({len(module['items'])} lessons)")
        generated += 1

print(f"\nDone. {generated} module files generated in {OUT}")

# ── Top-level index ───────────────────────────────────────────────────────────
index_parts = ['<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">',
               '<meta name="viewport" content="width=device-width, initial-scale=1">',
               '<title>CFA Level 1 — Modules</title><style>',
               'body{font-family:sans-serif;max-width:800px;margin:0 auto;padding:20px 16px 60px;color:#222;}',
               'h1{font-size:22px;color:#1a3a5c;border-bottom:2px solid #0770a3;padding-bottom:8px;}',
               'h2{font-size:16px;color:#0770a3;margin:28px 0 6px;}',
               'h3{font-size:13px;color:#666;text-transform:uppercase;letter-spacing:.4px;margin:14px 0 4px;}',
               'ul{margin:0 0 6px;padding-left:18px;}li{margin:3px 0;}',
               'a{color:#0770a3;text-decoration:none;font-size:14px;}a:hover{text-decoration:underline;}',
               '</style></head><body>',
               '<h1>CFA Level 1 Curriculum — Module Files</h1>']

for ch_idx, chapter in enumerate(chapters, 1):
    ch_slug = f"{ch_idx:02d}_{slugify(chapter['title'])}"
    index_parts.append(f'<h2>{chapter["title"]}</h2>')
    for mod_idx, module in enumerate(chapter["modules"], 1):
        if not module["items"]:
            continue
        mod_slug = f"{mod_idx:02d}_{slugify(module['title'])}"
        rel_path = f"{ch_slug}/{mod_slug}.html"
        index_parts.append(f'<h3>{module["title"]}</h3><ul>')
        index_parts.append(f'<li><a href="{rel_path}">{module["title"]}</a> ({len(module["items"])} lessons)</li>')
        index_parts.append('</ul>')

index_parts.append('</body></html>')

with open(OUT / "index.html", "w", encoding="utf-8") as f:
    f.write("\n".join(index_parts))

print("Top-level index written.")
