#!/usr/bin/env python3
"""
Combine per-lesson HTML files into one HTML per module for CIPM-LV1.
- Flashcards: show all cards with front+back visible simultaneously
- Knowledge Check: reveal all answers (correct highlighted, explanations shown)
- Remove navigation bars and interactive scripts
"""

import os
import re
from pathlib import Path
from bs4 import BeautifulSoup, Tag

SRC = Path("/Users/tarai/Research/ExamPrep/dist/CIPM-LV1")
OUT = Path("/Users/tarai/Research/ExamPrep/dist/CIPM/LV1/view_by_module")
OUT.mkdir(parents=True, exist_ok=True)

# ── Parse index.html ───────────────────────────────────────────────────────────
with open(SRC / "index.html", encoding="utf-8") as f:
    idx = BeautifulSoup(f, "html.parser")

# Structure: course-section > h2 (chapter), module-section > h3 (module), lesson-list > li > a
chapters = []
for cs in idx.find_all("div", class_="course-section"):
    chapter_title = cs.find("h2").get_text(strip=True)
    modules = []
    for ms in cs.find_all("div", class_="module-section"):
        mod_title = ms.find("h3").get_text(strip=True)
        items = []
        for li in ms.find_all("li"):
            a = li.find("a")
            if a:
                items.append((a["href"], a.get_text(strip=True)))
        modules.append({"title": mod_title, "items": items})
    chapters.append({"title": chapter_title, "modules": modules})

total_modules = sum(len(c["modules"]) for c in chapters)
total_items   = sum(len(m["items"]) for c in chapters for m in c["modules"])
print(f"Parsed: {len(chapters)} chapters, {total_modules} modules, {total_items} items")

# ── CSS ───────────────────────────────────────────────────────────────────────
COMMON_CSS = """
body {
  font-family: 'Lato', 'Helvetica Neue', Arial, sans-serif;
  font-size: 15px; line-height: 1.65; color: #333;
  max-width: 880px; margin: 0 auto; padding: 24px 24px 60px;
  background: #fff;
}
h1 { font-size: 24px; color: #2d3b45; border-bottom: 3px solid #0770a3; padding-bottom: 10px; }
h3.lesson-title {
  font-size: 13px; color: #666; margin: 32px 0 8px;
  border-top: 1px solid #ddd; padding-top: 10px;
  text-transform: uppercase; letter-spacing: .5px; font-weight: 700;
}
hr.lesson-sep { border: none; border-top: 1px solid #e0e0e0; margin: 24px 0; }

/* Tables */
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 14px; }
th, td { border: 1px solid #ccc; padding: 7px 10px; vertical-align: top; text-align: left; }
th { background: #f0f4f7; font-weight: 600; }

/* Knowledge Check ── fully revealed */
.dp-qc { margin: 20px 0; border: 2px solid #0770a3; border-radius: 8px; overflow: hidden; }
.dp-qc > figcaption {
  background: #0770a3; color: #fff; padding: 10px 16px;
  font-weight: 700; font-size: 14px;
}
.dp-qc fieldset { border: none; margin: 0; padding: 16px; }
.dp-qc-question legend { font-size: 14px; font-weight: 600; margin-bottom: 10px; display: block; }
dl.dp-qc-answers { margin: 0; padding: 0; }
dt.dp-qc-answer {
  border: 2px solid #ddd; border-radius: 6px; margin-bottom: 8px;
  padding: 10px 14px; background: #fafafa; display: flex; align-items: flex-start; gap: 8px;
}
dt.dp-qc-answer input[type="radio"] { display: none; }
dt.dp-qc-answer label { flex: 1; margin: 0; cursor: default; }
dt.dp-qc-answer label p { margin: 0; }
dt.dp-qc-answer.qc-correct {
  border-color: #2e7d32; background: #e8f5e9;
}
dt.dp-qc-answer.qc-correct::before {
  content: "✓"; color: #2e7d32; font-weight: 900; font-size: 15px;
  margin-right: 4px; flex-shrink: 0;
}
dt.dp-qc-answer:not(.qc-correct) { color: #666; }
/* Hide the circular icon pseudo-element */
dt.dp-qc-answer::after { display: none !important; }
dd.dp-qc-response {
  display: block !important;
  padding: 8px 14px; margin: -4px 0 8px 0; font-size: 13px;
  border-radius: 0 0 5px 5px;
}
dd.dp-qc-response.dp-qc-correct {
  background: #e8f5e9; border: 2px solid #2e7d32; border-top: none;
}
dd.dp-qc-response:not(.dp-qc-correct) {
  background: #f5f5f5; border: 2px solid #bbb; border-top: none;
}
.dp-qc-answer-type { display: none; }
.qc-result-banner, .qc-reset-btn, a.dp-qc-submit { display: none !important; }
figure.dp-content-block { margin: 20px 0; }

/* Flashcards ── all cards shown, front then back */
.fc-card-static { margin: 10px 0 14px; border-radius: 8px; overflow: hidden;
  border: 1px solid #0770a3; }
.fc-card-static .fc-front { background: #f0f7fc; padding: 14px 18px;
  border-bottom: 1px solid #0770a3; font-weight: 600; }
.fc-card-static .fc-back  { background: #e8f5e9; padding: 14px 18px; }
.fc-card-static .fc-label { font-size: 11px; color: #888; text-transform: uppercase;
  letter-spacing: .5px; margin-bottom: 4px; }

/* Content blocks */
.cfa-curriculum-los-box {
  background: #eef5fb; border-left: 4px solid #0770a3;
  padding: 12px 16px; margin: 12px 0; border-radius: 0 4px 4px 0;
}
.cfa-curriculum-los-box h3 { margin: 0 0 6px; font-size: 14px; color: #0770a3; }
.cfa-curriculum-example-box { background: #fffbf0; border: 1px solid #e0cc88;
  border-radius: 6px; padding: 12px 16px; margin: 12px 0; }

/* Hide UI chrome */
#viewer-nav, .fc-hint, .fc-nav, nav.breadcrumb,
.flashcard-container > .controls,
.dp-popup-content, .dp-popover-content { display: none !important; }

/* Math */
.cfa-curriculum-display-formula-container { overflow-x: auto; margin: 12px 0; }

/* TOC */
.toc { background: #f5f8ff; border: 1px solid #c0d0e0; border-radius: 8px;
  padding: 14px 18px; margin-bottom: 28px; }
.toc h2 { margin-top: 0; font-size: 14px; color: #2d3b45; }
.toc ol { margin: 0; padding-left: 20px; }
.toc li { margin: 3px 0; font-size: 13px; }
.toc a { color: #0770a3; text-decoration: none; }
.toc a:hover { text-decoration: underline; }
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_content(href: str):
    """Load a lesson file and return the main content div, or None."""
    path = SRC / href
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    # CIPM uses div.page-wrapper; fallback to show-content (CFA style)
    el = soup.find("div", class_="page-wrapper")
    if not el:
        el = soup.find("div", class_="show-content")
    return el


def transform_flashcards(content: Tag) -> None:
    for container in content.find_all("div", class_="flashcard-container"):
        cards_data = []
        for card in container.find_all("div", class_="flashcard"):
            front = card.find("div", class_="front")
            back  = card.find("div", class_="back")
            cards_data.append((
                front.decode_contents() if front else "",
                back.decode_contents()  if back  else "",
            ))
        new_html = '<div class="fc-static-list">'
        for i, (f, b) in enumerate(cards_data, 1):
            new_html += (
                f'<div class="fc-card-static">'
                f'<div class="fc-front"><div class="fc-label">表 ({i}/{len(cards_data)})</div>{f}</div>'
                f'<div class="fc-back"><div class="fc-label">裏</div>{b}</div>'
                f'</div>'
            )
        new_html += '</div>'
        container.replace_with(BeautifulSoup(new_html, "html.parser"))
    for ctrl in content.find_all("div", class_="controls"):
        ctrl.decompose()


def transform_knowledge_checks(content: Tag) -> None:
    """Reveal correct answers and show all explanations."""
    # CIPM uses figure.dp-content-block > fieldset structure
    for qc in content.find_all(class_="dp-qc"):
        # Reveal responses
        for dd in qc.find_all("dd", class_="dp-qc-response"):
            dd["style"] = "display:block"
            # Remove d-none if present
            cls = [c for c in dd.get("class", []) if c != "d-none"]
            dd["class"] = cls
        # Find correct dt and mark it
        for dt in qc.find_all("dt", class_="dp-qc-answer"):
            if "dp-qc-correct" in dt.get("class", []):
                existing = dt.get("class", [])
                if "qc-correct" not in existing:
                    dt["class"] = existing + ["qc-correct"]
        # Remove submit button
        for btn in qc.find_all("a", class_="dp-qc-submit"):
            btn.decompose()


def clean_content(content: Tag) -> None:
    for el in content.find_all(id="viewer-nav"):
        el.decompose()
    for el in content.find_all("script"):
        el.decompose()
    for el in content.find_all("style"):
        el.decompose()
    for el in content.find_all(class_="fc-hint"):
        el.decompose()
    for el in content.find_all(class_="fc-nav"):
        el.decompose()
    for el in content.find_all("nav", class_="breadcrumb"):
        el.decompose()
    # Remove viewer-nav div
    for el in content.find_all("div", id="viewer-nav"):
        el.decompose()


def build_module_html(chapter_title: str, module_title: str, items) -> str:
    lessons_parts = []
    toc_items = []

    for idx_i, (href, label) in enumerate(items):
        content = load_content(href)
        if content is None:
            continue

        anchor = f"lesson-{idx_i}"
        toc_items.append((anchor, label))

        transform_flashcards(content)
        transform_knowledge_checks(content)
        clean_content(content)

        lessons_parts.append(
            f'<hr class="lesson-sep" id="{anchor}">'
            f'<h3 class="lesson-title">{label}</h3>'
            + content.decode_contents()
        )

    toc_html = '<div class="toc"><h2>目次 (Table of Contents)</h2><ol>'
    for anchor, label in toc_items:
        toc_html += f'<li><a href="#{anchor}">{label}</a></li>'
    toc_html += '</ol></div>'

    full_title = f"{chapter_title} — {module_title}"
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
{"".join(lessons_parts)}
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

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

print(f"\nDone. {generated} module files in {OUT}")

# ── Top-level index ───────────────────────────────────────────────────────────
idx_parts = [
    '<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    '<title>CIPM Level 1 — Modules</title><style>',
    'body{font-family:sans-serif;max-width:800px;margin:0 auto;padding:20px 16px 60px;color:#333;}',
    'h1{font-size:22px;color:#2d3b45;border-bottom:2px solid #0770a3;padding-bottom:8px;}',
    'h2{font-size:16px;color:#0770a3;margin:28px 0 6px;}',
    'h3{font-size:13px;color:#666;text-transform:uppercase;letter-spacing:.4px;margin:14px 0 4px;}',
    'ul{margin:0 0 6px;padding-left:18px;}li{margin:3px 0;}',
    'a{color:#0770a3;text-decoration:none;font-size:14px;}a:hover{text-decoration:underline;}',
    '</style></head><body>',
    '<h1>CIPM Level 1 Curriculum — Module Files</h1>',
]
for ch_idx, chapter in enumerate(chapters, 1):
    ch_slug = f"{ch_idx:02d}_{slugify(chapter['title'])}"
    idx_parts.append(f'<h2>{chapter["title"]}</h2>')
    for mod_idx, module in enumerate(chapter["modules"], 1):
        if not module["items"]:
            continue
        mod_slug = f"{mod_idx:02d}_{slugify(module['title'])}"
        rel = f"{ch_slug}/{mod_slug}.html"
        idx_parts.append(f'<h3>{module["title"]}</h3><ul>')
        idx_parts.append(f'<li><a href="{rel}">{module["title"]}</a> ({len(module["items"])} lessons)</li>')
        idx_parts.append('</ul>')
idx_parts.append('</body></html>')

with open(OUT / "index.html", "w", encoding="utf-8") as f:
    f.write("\n".join(idx_parts))
print("Index written.")
