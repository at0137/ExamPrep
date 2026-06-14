"""
Build a standalone offline viewer from saved CIPM HTML files.
Output: CIPM/LV1/viewer/ with index.html and per-lesson pages.
"""

import re
import json
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "CIPM" / "LV1" / "translated_html"
OUT_DIR = Path(__file__).parent.parent.parent / "dist" / "CIPM-LV1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SHARED_CSS = """
body { font-family: 'Lato', 'Helvetica Neue', Arial, sans-serif; margin: 0; background: #f0f2f5; color: #333; font-size: 16px; line-height: 1.6; }
.page-wrapper { max-width: 900px; margin: 0 auto; background: #fff; padding: 32px 48px 64px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }
nav.breadcrumb { font-size: 13px; color: #666; margin-bottom: 20px; }
nav.breadcrumb a { color: #0770a3; text-decoration: none; }
nav.breadcrumb a:hover { text-decoration: underline; }

/* Reading content */
.dp-wrapper { margin: 0; }
.dp-header { margin-bottom: 24px; }
.dp-heading { font-size: 22px; font-weight: 700; color: #2d3b45; margin: 0; line-height: 1.3; }
.dp-header-pre { display: block; font-size: 13px; font-weight: 400; color: #666; margin-bottom: 4px; }
.dp-hr-solid-light { border: none; border-top: 1px solid #ddd; margin: 20px 0; }
.dp-flat-sections p { margin: 0 0 14px; }
.dp-flat-sections ul, .dp-flat-sections ol { margin: 0 0 14px 24px; }
.dp-flat-sections li { margin-bottom: 6px; }
.dp-flat-sections h3 { font-size: 17px; font-weight: 700; color: #2d3b45; margin: 24px 0 8px; }
.dp-flat-sections table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14px; }
.dp-flat-sections th, .dp-flat-sections td { border: 1px solid #ccc; padding: 8px 12px; text-align: left; }
.dp-flat-sections th { background: #f0f4f7; font-weight: 600; }
.dp-flat-sections figure { margin: 20px 0; }
.dp-flat-sections img { max-width: 100%; height: auto; }

/* Learning Outcomes box */
.cfa-curriculum-los-box { background: #eef5fb; border-left: 4px solid #0770a3; padding: 14px 18px; margin: 0 0 20px; border-radius: 0 4px 4px 0; }
.cfa-curriculum-los-box h3 { margin: 0 0 8px; font-size: 15px; color: #0770a3; }
.cfa-curriculum-los-box ul { margin: 0 0 0 20px; }
.cfa-curriculum-los-box li { font-size: 14px; margin-bottom: 4px; }

/* ── Knowledge Check ── */
figure.dp-content-block { margin: 36px 0 0; border: 2px solid #0770a3; border-radius: 8px; overflow: hidden; }
figure.dp-content-block > figcaption {
  background: #0770a3; color: #fff; padding: 12px 18px;
  font-weight: 700; font-size: 15px; display: flex; align-items: center; gap: 8px;
  letter-spacing: .3px;
}
figure.dp-content-block > figcaption i { opacity: .85; }

/* fieldset reset */
.dp-qc fieldset { border: none; margin: 0; padding: 20px; }
.dp-qc-question { margin-bottom: 18px; }
.dp-qc-question legend { font-size: 15px; font-weight: 500; padding: 0; float: left; width: 100%; }
.dp-qc-question p { margin: 0 0 8px; }
.cfa-curriculum-question-with-label { font-size: 15px; }
.cfa-curriculum-option-label { font-weight: 700; }

/* Answer choices — radio hidden, dt acts as button */
dl.dp-qc-answers { margin: 0; padding: 0; list-style: none; }
dt.dp-qc-answer {
  border: 2px solid #ccc; border-radius: 6px; margin-bottom: 10px;
  padding: 12px 16px; cursor: pointer; background: #fafafa;
  transition: border-color .15s, background .15s;
  display: flex; align-items: flex-start; gap: 10px; position: relative;
}
dt.dp-qc-answer:hover { border-color: #0770a3; background: #f0f7fc; }
dt.dp-qc-answer label { cursor: pointer; flex: 1; margin: 0; }
dt.dp-qc-answer label p { margin: 0; }
/* hide the actual radio */
dt.dp-qc-answer input[type="radio"] { position: absolute; opacity: 0; pointer-events: none; }
/* status icon slot */
dt.dp-qc-answer::after {
  content: ''; width: 22px; height: 22px; border-radius: 50%;
  border: 2px solid #ccc; flex-shrink: 0; margin-top: 1px;
  display: inline-block;
}
/* selected wrong */
dt.dp-qc-answer.qc-wrong {
  border-color: #c62828; background: #ffebee; cursor: default;
}
dt.dp-qc-answer.qc-wrong::after {
  content: '✗'; border-color: #c62828; background: #c62828;
  color: #fff; font-size: 13px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
/* correct answer revealed */
dt.dp-qc-answer.qc-correct {
  border-color: #2e7d32; background: #e8f5e9; cursor: default;
}
dt.dp-qc-answer.qc-correct::after {
  content: '✓'; border-color: #2e7d32; background: #2e7d32;
  color: #fff; font-size: 13px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
dt.dp-qc-answer.qc-disabled { cursor: default; }

/* Response / explanation */
dd.dp-qc-response {
  display: none !important;   /* overridden by JS with style.display */
  margin: -4px 0 10px 0; padding: 12px 16px;
  border-radius: 0 0 6px 6px; font-size: 14px; line-height: 1.55;
}
dd.dp-qc-response.dp-qc-correct {
  background: #e8f5e9; border: 2px solid #2e7d32; border-top: none;
}
dd.dp-qc-response:not(.dp-qc-correct) {
  background: #ffebee; border: 2px solid #c62828; border-top: none;
}
.dp-qc-answer-type { display: none; } /* icons handled by dt::after */
.dp-qc-content p { margin: 0 0 6px; }
.cfa-curriculum-option-label { font-weight: 700; }

/* Result banner */
.qc-result-banner {
  margin: 0 0 16px; padding: 12px 18px; border-radius: 6px;
  font-weight: 700; font-size: 15px; display: flex; align-items: center; gap: 10px;
}
.qc-result-banner.correct { background: #e8f5e9; color: #1b5e20; border: 2px solid #2e7d32; }
.qc-result-banner.wrong   { background: #ffebee; color: #b71c1c; border: 2px solid #c62828; }
.qc-result-banner .icon   { font-size: 20px; }

/* Reset button */
.qc-reset-btn {
  margin-top: 14px; background: #546e7a; color: #fff; border: none;
  padding: 7px 18px; border-radius: 5px; cursor: pointer; font-size: 13px;
  display: block;
}
.qc-reset-btn:hover { background: #37474f; }

/* Popover (glossary) */
.dp-popover-trigger { color: #0770a3; border-bottom: 1px dotted #0770a3; cursor: help; position: relative; }
.dp-popup-content {
  display: none; position: absolute; z-index: 100; background: #fff;
  border: 1px solid #ccc; border-radius: 4px; padding: 8px 12px;
  font-size: 13px; max-width: 280px; box-shadow: 0 2px 8px rgba(0,0,0,.15);
  left: 0; top: 1.6em; white-space: normal;
}
.dp-popover-trigger.open .dp-popup-content { display: block; }

/* ── Flashcard ── */
.flashcard { cursor: pointer; margin: 12px 0; }
.flashcard .front,
.flashcard .back {
  padding: 24px 20px; border: 2px solid #0770a3; border-radius: 8px;
  min-height: 100px; display: flex; align-items: center; justify-content: center;
  text-align: center; font-size: 15px; line-height: 1.5;
}
.flashcard .front { background: #f0f7fc; }
.flashcard .back  { background: #e8f5e9; border-color: #2e7d32; display: none; }
.flashcard.flipped .front { display: none; }
.flashcard.flipped .back  { display: flex; }
.fc-hint { text-align: center; font-size: 12px; color: #888; margin: 4px 0 10px; }
.fc-nav {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; margin-bottom: 16px;
}
.fc-nav button {
  background: #0770a3; color: #fff; border: none;
  padding: 7px 18px; border-radius: 5px; cursor: pointer; font-size: 14px;
}
.fc-nav button:disabled { background: #bbb; cursor: default; }
.fc-nav .fc-counter { font-size: 13px; color: #555; }

/* Fixed bottom nav */
#viewer-nav {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 99999;
  background: rgba(30,50,70,.93); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px; gap: 8px;
  font-family: sans-serif; font-size: 13px;
}
#viewer-nav a {
  color: #fff; text-decoration: none;
  background: rgba(255,255,255,.15); border-radius: 5px;
  padding: 6px 14px; white-space: nowrap;
}
#viewer-nav a:hover { background: rgba(255,255,255,.28); }
#viewer-nav a.disabled { opacity: .3; pointer-events: none; }
#viewer-nav .title {
  color: #cde; font-size: 12px; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; flex: 1; text-align: center;
}
body { padding-bottom: 52px; }

/* Index page */
.index-header { background: #2d3b45; color: #fff; padding: 28px 40px; margin-bottom: 32px; }
.index-header h1 { margin: 0 0 6px; font-size: 26px; }
.index-header p { margin: 0; color: #aec7d8; font-size: 14px; }
.course-section { margin-bottom: 36px; }
.course-section h2 { font-size: 18px; color: #2d3b45; border-bottom: 2px solid #0770a3; padding-bottom: 6px; margin-bottom: 14px; }
.module-section { margin-bottom: 20px; }
.module-section h3 { font-size: 13px; color: #666; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; margin: 0 0 8px; }
ul.lesson-list { list-style: none; margin: 0; padding: 0; }
ul.lesson-list li { margin-bottom: 5px; }
ul.lesson-list li a { color: #0770a3; text-decoration: none; font-size: 14px; display: inline-flex; align-items: center; gap: 7px; }
ul.lesson-list li a:hover { text-decoration: underline; }
ul.lesson-list li a.has-quiz::after {
  content: "KC"; font-size: 10px; background: #fff3e0; color: #e65100;
  border: 1px solid #ffb74d; border-radius: 3px; padding: 0 5px;
  font-weight: 700; letter-spacing: .3px;
}
"""

SHARED_JS = """
(function() {
  // ── Knowledge Check quiz ──
  document.querySelectorAll('.dp-qc').forEach(function(qc) {
    var answered = false;
    var answers  = Array.from(qc.querySelectorAll('dt.dp-qc-answer'));

    // Find response dd by data-response id on the radio inside each dt
    function getResponse(dt) {
      var radio = dt.querySelector('input[type="radio"]');
      if (!radio) return null;
      var id = radio.getAttribute('data-response');
      return id ? document.getElementById(id) : dt.nextElementSibling;
    }

    function isCorrect(dt) {
      var radio = dt.querySelector('input[type="radio"]');
      return radio ? radio.value === 'true' : dt.classList.contains('dp-qc-correct');
    }

    // Insert result banner placeholder before the dl
    var dl = qc.querySelector('dl.dp-qc-answers');
    var banner = document.createElement('div');
    banner.className = 'qc-result-banner';
    banner.style.display = 'none';
    if (dl) dl.parentNode.insertBefore(banner, dl);

    // Insert reset button after the dl
    var resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'qc-reset-btn';
    resetBtn.textContent = '↩ もう一度';
    resetBtn.style.display = 'none';
    if (dl) dl.parentNode.insertBefore(resetBtn, dl.nextSibling);

    function revealAnswer(selectedDt) {
      if (answered) return;
      answered = true;
      var correct = isCorrect(selectedDt);

      // Style each answer dt and show its response
      answers.forEach(function(dt) {
        dt.classList.add('qc-disabled');
        var resp = getResponse(dt);
        if (isCorrect(dt)) {
          dt.classList.add('qc-correct');
          if (resp) resp.style.display = 'block';
        } else if (dt === selectedDt && !correct) {
          dt.classList.add('qc-wrong');
          if (resp) resp.style.display = 'block';
        }
      });

      // Show result banner
      banner.style.display = 'flex';
      if (correct) {
        banner.className = 'qc-result-banner correct';
        banner.innerHTML = '<span class="icon">✓</span> 正解です！';
      } else {
        banner.className = 'qc-result-banner wrong';
        // Find correct label text
        var correctDt = answers.find(function(d) { return isCorrect(d); });
        var correctLabel = correctDt ? correctDt.querySelector('label') : null;
        var correctText = correctLabel ? correctLabel.textContent.trim() : '';
        banner.innerHTML = '<span class="icon">✗</span> 不正解。正解：' + correctText;
      }

      resetBtn.style.display = 'block';
    }

    // Click on dt or label
    answers.forEach(function(dt) {
      dt.addEventListener('click', function() { revealAnswer(dt); });
      dt.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); revealAnswer(dt); }
      });
      dt.setAttribute('tabindex', '0');
      dt.setAttribute('role', 'button');
    });

    // Reset
    resetBtn.addEventListener('click', function() {
      answered = false;
      answers.forEach(function(dt) {
        dt.classList.remove('qc-correct', 'qc-wrong', 'qc-disabled');
        var resp = getResponse(dt);
        if (resp) resp.style.display = 'none';
      });
      banner.style.display = 'none';
      resetBtn.style.display = 'none';
    });
  });

  // ── Flashcards ──
  var cards = Array.from(document.querySelectorAll('.flashcard'));
  if (cards.length) {
    var current = 0;

    cards.forEach(function(card) {
      card.addEventListener('click', function() {
        card.classList.toggle('flipped');
      });
    });

    cards[0].insertAdjacentHTML('afterend', '<p class="fc-hint">タップで裏面を表示</p>');

    var nav = document.createElement('div');
    nav.className = 'fc-nav';
    nav.innerHTML =
      '<button id="fc-prev" disabled>← 前へ</button>' +
      '<span class="fc-counter" id="fc-count">1 / ' + cards.length + '</span>' +
      '<button id="fc-next">次へ →</button>';
    cards[0].parentNode.insertBefore(nav, cards[0]);

    function showCard(n) {
      cards[current].style.display = 'none';
      cards[current].classList.remove('flipped');
      current = n;
      cards[current].style.display = '';
      document.getElementById('fc-count').textContent = (current+1) + ' / ' + cards.length;
      document.getElementById('fc-prev').disabled = current === 0;
      document.getElementById('fc-next').disabled = current === cards.length - 1;
    }

    document.getElementById('fc-prev').addEventListener('click', function() {
      if (current > 0) showCard(current - 1);
    });
    document.getElementById('fc-next').addEventListener('click', function() {
      if (current < cards.length - 1) showCard(current + 1);
    });
  }

  // ── Glossary popovers ──
  document.querySelectorAll('.dp-popover-trigger').forEach(function(trigger) {
    var targetId = trigger.getAttribute('aria-describedby');
    if (!targetId) return;
    var popup = document.getElementById(targetId);
    if (!popup) return;
    popup.classList.add('dp-popup-content');
    popup.style.display = 'none';
    trigger.style.position = 'relative';
    trigger.appendChild(popup);

    trigger.addEventListener('click', function(e) {
      e.preventDefault();
      trigger.classList.toggle('open');
    });

    // Close on outside click
    document.addEventListener('click', function(e) {
      if (!trigger.contains(e.target)) trigger.classList.remove('open');
    });
  });
})();
"""


def extract_content(html: str) -> tuple:
    """Extract main content div and title from saved HTML."""
    # Try to find the populated show-content div
    sc_match = re.search(
        r'<div[^>]+class="[^"]*show-content[^"]*"[^>]*>(.*?)</div>\s*\n\s*<div id="assign-to',
        html, re.DOTALL
    )
    if sc_match:
        content = sc_match.group(1).strip()
    else:
        # Fallback: look for dp-wrapper directly
        dp_match = re.search(r'(<div[^>]+class="dp-wrapper[^"]*".*?</div>)\s*\n', html, re.DOTALL)
        content = dp_match.group(1) if dp_match else ""

    # Extract title from h1 or dp-heading
    title_match = re.search(r'<h[12][^>]*class="[^"]*(?:dp-heading|page-title)[^"]*"[^>]*>(.*?)</h[12]>', content, re.DOTALL)
    if title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
    else:
        title_match2 = re.search(r'<title>(.*?)</title>', html)
        title = re.sub(r'<[^>]+>', '', title_match2.group(1)).strip() if title_match2 else "Untitled"

    return content, title


def has_quiz(content: str) -> bool:
    return 'dp-qc' in content


def page_html(title: str, content: str, breadcrumb: str, prev_link: str, next_link: str) -> str:
    nav_bar = f"""<div id="viewer-nav">
  <a href="index.html">☰ Index</a>
  <a href="{prev_link}" {"" if prev_link else 'class="disabled"'}>← 前へ</a>
  <span class="title">{title}</span>
  <a href="{next_link}" {"" if next_link else 'class="disabled"'}>次へ →</a>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>{SHARED_CSS}</style>
</head>
<body>
<div class="page-wrapper">
<nav class="breadcrumb">{breadcrumb}</nav>
{content}
</div>
{nav_bar}
<script>{SHARED_JS}</script>
</body>
</html>"""


def index_html(courses: dict, module_display: dict) -> str:
    total_pages = sum(len(items) for c in courses.values() for items in c.values())
    total_kc = sum(1 for c in courses.values() for items in c.values() for (_, _, has_kc) in items if has_kc)

    body = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CIPM LV1 Curriculum</title>
<style>{SHARED_CSS}</style>
</head>
<body>
<div class="index-header">
  <h1>CIPM Level 1 Curriculum</h1>
  <p>{total_pages} lessons &nbsp;·&nbsp; {total_kc} pages with Knowledge Check</p>
</div>
<div class="page-wrapper" style="box-shadow:none; padding-top:0;">
"""
    for course_name, modules in courses.items():
        body += f'<div class="course-section"><h2>{course_name}</h2>\n'
        for mod_key, items in modules.items():
            display = module_display[course_name][mod_key]
            body += f'<div class="module-section"><h3>{display}</h3><ul class="lesson-list">\n'
            for (fname, title, has_kc) in items:
                kc_class = ' has-quiz' if has_kc else ''
                body += f'<li><a href="{fname}" class="{kc_class.strip()}">{title}</a></li>\n'
            body += '</ul></div>\n'
        body += '</div>\n'

    body += '</div></body></html>'
    return body


def get_course_name(filename: str) -> str:
    course_map = {
        '1366': 'Performance Evaluation: Rate-of-Return Measurement',
        '1367': 'Return Attribution and Benchmarks',
        '1368': 'Risk Measurement and Attribution',
        '1369': 'Investment Performance Appraisal',
        '1370': 'Investment Performance Presentation and GIPS',
    }
    m = re.search(r'courses_(\d+)_', filename)
    return course_map.get(m.group(1) if m else '', 'Unknown') if m else 'Unknown'


def _normalize_module_name(name: str) -> str:
    name = re.sub(r'&amp;', 'and', name)
    name = re.sub(r',\s+and\b', ' and', name)
    name = re.sub(r'[–—]', '-', name)
    name = name.replace('\xa0', ' ')
    name = re.sub(r'\s+', ' ', name).strip()
    m = re.match(r'(Module \d+:)\s*(.*)', name, re.IGNORECASE)
    if m:
        rest = m.group(2).strip().title()
        for word in ('And', 'Of', 'The', 'For', 'In', 'A', 'An', 'With', 'To', 'At', 'By', 'From'):
            rest = re.sub(rf'\b{word}\b', word.lower(), rest)
        rest = re.sub(r'\(([^)]{1,6})\)', lambda x: '(' + x.group(1).upper() + ')', rest)
        rest = rest[0].upper() + rest[1:] if rest else rest
        name = m.group(1) + ' ' + rest
    return name


def _extract_module_num(filename: str):
    m = re.search(r'_items_\d+_(\d{3,4})_', filename)
    if not m:
        return None
    return int(m.group(1)) // 100


def _extract_info_from_header(html: str):
    m = re.search(r'<header[^>]*class="dp-header[^"]*"[^>]*>(.*?)</header>', html, re.DOTALL)
    if not m:
        nm = re.search(r'モジュール(\d+)', html)
        return (int(nm.group(1)), None) if nm else (None, None)
    text = re.sub(r'<[^>]+>', ' ', m.group(1))
    nm = re.search(r'モジュール(\d+)', text)
    if not nm:
        return None, None
    module_num = int(nm.group(1))
    before_pipe = text.split('｜')[0]
    topic_m = re.search(r'[（(]([^）)]{3,60})[）)]', before_pipe)
    topic = topic_m.group(1).strip() if topic_m else None
    return module_num, topic


def _extract_topic_from_wrapper_title(html: str):
    m = re.search(
        r'<div[^>]+class="dp-wrapper[^"]*"[^>]+title="'
        r'(?:Learning Outcomes|Glossary|Flashcards)[^:]*:\s*([^"]+)"',
        html, re.IGNORECASE
    )
    return m.group(1).strip() if m else None


def get_module_name(html: str, filename: str = '', module_map=None) -> str:
    course_id = None
    if filename:
        cm = re.search(r'courses_(\d+)_', filename)
        if cm:
            course_id = cm.group(1)

    def _map_lookup(mod_num):
        if module_map and course_id and mod_num is not None:
            return module_map.get((course_id, mod_num))
        return None

    result = _map_lookup(_extract_module_num(filename))
    if result:
        return result

    m = re.search(r'<span class="dp-header-pre">([^<]+)</span>', html)
    if m:
        raw = m.group(1).strip()
        nm = re.match(r'Module\s+(\d+):', raw, re.IGNORECASE)
        if nm:
            result = _map_lookup(int(nm.group(1)))
            if result:
                return result
        return _normalize_module_name(raw)

    mod_num, hdr_topic = _extract_info_from_header(html)
    if mod_num is not None:
        result = _map_lookup(mod_num)
        if result:
            return result
        topic = _extract_topic_from_wrapper_title(html) or hdr_topic
        if topic:
            return _normalize_module_name(f'Module {mod_num}: {topic}')
        return f'Module {mod_num}'

    return 'General'


def main():
    lesson_files = sorted([
        f for f in RAW_DIR.glob("courses_*_modules_items_*.html")
        if '{{' not in f.name and '_debug_' not in f.name
        and 'duplicate' not in f.name
    ], key=lambda f: (
        re.search(r'courses_(\d+)_', f.name).group(1),
        int(re.search(r'_items_(\d+)_', f.name).group(1))
        if re.search(r'_items_(\d+)_', f.name) else 0
    ))

    print(f"Processing {len(lesson_files)} lesson files...")

    # First pass: cache HTML and build module_map
    html_cache = {}
    for f in lesson_files:
        html_cache[f.name] = f.read_text(errors='ignore')

    module_map = {}
    for f in lesson_files:
        html = html_cache[f.name]
        course_m = re.search(r'courses_(\d+)_', f.name)
        if not course_m:
            continue
        cid = course_m.group(1)

        pre_m = re.search(r'<span class="dp-header-pre">([^<]+)</span>', html)
        mod_num_file = _extract_module_num(f.name)
        if pre_m and mod_num_file is not None:
            key = (cid, mod_num_file)
            if key not in module_map:
                module_map[key] = _normalize_module_name(pre_m.group(1).strip())

        mod_num_hdr, hdr_topic = _extract_info_from_header(html)
        topic = _extract_topic_from_wrapper_title(html) or hdr_topic
        if mod_num_hdr is not None and topic:
            key = (cid, mod_num_hdr)
            if key not in module_map:
                module_map[key] = _normalize_module_name(f'Module {mod_num_hdr}: {topic}')

    # Second pass: extract content and metadata
    lessons = []
    for f in lesson_files:
        html = html_cache[f.name]
        content, title = extract_content(html)
        if not content:
            print(f"  [skip] no content: {f.name}")
            continue
        lessons.append({
            'src': f,
            'content': content,
            'title': title,
            'has_kc': has_quiz(content),
            'course': get_course_name(f.name),
            'module': get_module_name(html, f.name, module_map),
        })

    # Build course->module->lessons index (insertion order, lowercase key dedup)
    courses = {}
    module_display = {}
    all_out_names = []

    for lesson in lessons:
        out_name = lesson['src'].name
        all_out_names.append(out_name)
        course = lesson['course']
        mod_key = lesson['module'].lower()
        courses.setdefault(course, {}).setdefault(mod_key, []).append(
            (out_name, lesson['title'], lesson['has_kc'])
        )
        module_display.setdefault(course, {}).setdefault(mod_key, lesson['module'])

    # Third pass: write lesson HTML files
    for i, lesson in enumerate(lessons):
        out_name = all_out_names[i]
        prev_link = all_out_names[i - 1] if i > 0 else ''
        next_link = all_out_names[i + 1] if i < len(lessons) - 1 else ''
        bc = f'<a href="index.html">Index</a> › {lesson["course"]} › {lesson["module"]}'

        html_out = page_html(lesson['title'], lesson['content'], bc, prev_link, next_link)
        (OUT_DIR / out_name).write_text(html_out, encoding='utf-8')

        kc_marker = ' [KC]' if lesson['has_kc'] else ''
        print(f"  [{i+1}/{len(lessons)}] {lesson['title'][:60]}{kc_marker}")

    # Write index
    idx = index_html(courses, module_display)
    (OUT_DIR / 'index.html').write_text(idx, encoding='utf-8')

    print(f"\nDone. Open: {OUT_DIR}/index.html")
    print(f"Pages with Knowledge Check: {sum(1 for l in lessons if l['has_kc'])}")


if __name__ == '__main__':
    main()
