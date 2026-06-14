"""
build_cfa_viewer.py — Add navigation to CFA L1 translated HTML files.

Copies translated HTML as-is (preserving all Canvas styling) and injects
a minimal navigation bar (index / prev / next) into each page.
Also generates a simple index.html.

Usage:
    python3 scripts/build_cfa_viewer.py

Serve for smartphone (same WiFi):
    cd CFA/LV1/viewer && python3 -m http.server 8080
    # then open http://<your-mac-ip>:8080 on phone
"""

import re
import json
from pathlib import Path

TRANSLATED_DIR = Path(__file__).parent.parent / "CFA" / "LV1" / "translated_html"
OUT_DIR        = Path(__file__).parent.parent.parent / "dist" / "CFA-LV1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NAV_CSS = """
<style id="viewer-nav-style">
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

/* Bootstrap utility missing from Canvas CDN CSS */
.d-none { display: none !important; }
/* Hide all KC responses by default regardless of d-none */
dd.dp-qc-response { display: none !important; }
dd.dp-qc-response.qc-show { display: block !important; }
/* Canvas elements that are normally hidden without Canvas CSS */
.dp-popup-content,
.dp-popover-content,
.dp-icon-content,
.screenreader-only,
[style*="display: none"] { display: none !important; }

/* ── Knowledge Check ── */
dt.dp-qc-answer {
  cursor: pointer !important;
  -webkit-tap-highlight-color: rgba(7,112,163,0.15);
  touch-action: manipulation;
  user-select: none;
  -webkit-user-select: none;
}
dt.dp-qc-answer.qc-selected { background: #e3f2fd !important; outline: 2px solid #0770a3; }
dt.dp-qc-answer.qc-correct-reveal { background: #e8f5e9 !important; outline: 2px solid #2e7d32; }
dt.dp-qc-answer.qc-wrong-reveal   { background: #ffebee !important; outline: 2px solid #c62828; }
dd.dp-qc-response.qc-show { display: block !important; }
.qc-result-banner {
  display: none; padding: 10px 16px; border-radius: 6px; margin: 8px 0;
  font-weight: 700; font-size: 14px;
}
.qc-result-banner.correct { background: #e8f5e9; color: #1b5e20; border: 2px solid #2e7d32; }
.qc-result-banner.wrong   { background: #ffebee; color: #b71c1c; border: 2px solid #c62828; }
.qc-reset-btn {
  display: none; margin: 8px 0; background: #546e7a; color: #fff; border: none;
  padding: 6px 16px; border-radius: 5px; cursor: pointer; font-size: 13px;
}
</style>
"""

INTERACTIVE_JS = """
<script id="viewer-interactive">
(function() {

  // ── Knowledge Check ──
  // Use a single state map keyed by qc element
  var qcStates = new Map();

  document.querySelectorAll('.dp-qc').forEach(function(qc) {
    var dts = Array.from(qc.querySelectorAll('dt.dp-qc-answer'));
    if (!dts.length) return;

    var state = { answered: false, selectedIdx: -1, dts: dts };
    qcStates.set(qc, state);

    var submitBtn = qc.querySelector('a.dp-qc-submit');
    var dl = qc.querySelector('dl.dp-qc-answers');

    var banner = document.createElement('div');
    banner.className = 'qc-result-banner';
    (submitBtn || dl).parentNode.insertBefore(banner, submitBtn || dl);

    var resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'qc-reset-btn';
    resetBtn.textContent = '↩ もう一度';
    banner.after(resetBtn);

    state.banner = banner;
    state.resetBtn = resetBtn;
    state.submitBtn = submitBtn;

    resetBtn.addEventListener('click', function() { resetQc(qc); });
  });

  function selectAnswer(qc, idx) {
    var s = qcStates.get(qc);
    if (!s || s.answered) return;
    s.selectedIdx = idx;
    s.dts.forEach(function(d) { d.classList.remove('qc-selected'); });
    s.dts[idx].classList.add('qc-selected');
  }

  function revealAnswer(qc) {
    var s = qcStates.get(qc);
    if (!s || s.answered) return;
    s.answered = true;

    var idx = s.selectedIdx;
    var correct = idx >= 0 && s.dts[idx].classList.contains('dp-qc-correct');

    s.dts.forEach(function(dt, i) {
      dt.classList.remove('qc-selected');
      dt.style.pointerEvents = 'none';
      var dd = dt.nextElementSibling;
      if (dt.classList.contains('dp-qc-correct')) {
        dt.classList.add('qc-correct-reveal');
        if (dd) { dd.classList.remove('d-none'); dd.classList.add('qc-show'); }
      } else if (i === idx) {
        dt.classList.add('qc-wrong-reveal');
        if (dd) { dd.classList.remove('d-none'); dd.classList.add('qc-show'); }
      }
    });

    s.banner.style.display = 'block';
    s.banner.className = 'qc-result-banner ' + (correct ? 'correct' : 'wrong');
    s.banner.textContent = idx < 0 ? '選択肢を選んでください' : (correct ? '✓ 正解！' : '✗ 不正解');
    if (s.submitBtn) s.submitBtn.style.display = 'none';
    s.resetBtn.style.display = 'inline-block';
  }

  function resetQc(qc) {
    var s = qcStates.get(qc);
    if (!s) return;
    s.answered = false;
    s.selectedIdx = -1;
    s.dts.forEach(function(dt) {
      dt.classList.remove('qc-selected', 'qc-correct-reveal', 'qc-wrong-reveal');
      dt.style.pointerEvents = '';
      var dd = dt.nextElementSibling;
      if (dd) { dd.classList.remove('qc-show'); dd.classList.add('d-none'); }
    });
    s.banner.style.display = 'none';
    s.resetBtn.style.display = 'none';
    if (s.submitBtn) s.submitBtn.style.display = '';
  }

  // Single document-level delegation — catches taps anywhere inside dt or submit
  document.addEventListener('click', function(e) {
    var dt = e.target.closest('dt.dp-qc-answer');
    var submit = e.target.closest('a.dp-qc-submit');
    if (dt) {
      var qc = dt.closest('.dp-qc');
      var s = qcStates.get(qc);
      if (s) selectAnswer(qc, s.dts.indexOf(dt));
    } else if (submit) {
      e.preventDefault();
      var qc = submit.closest('.dp-qc');
      if (qc) revealAnswer(qc);
    }
  });

  // ── Flashcards ──
  var cards = Array.from(document.querySelectorAll('.flashcard'));
  if (!cards.length) return;

  var current = 0;

  cards.forEach(function(card) {
    card.addEventListener('click', function() {
      card.classList.toggle('flipped');
    });
  });

  // Add hint under first card
  cards[0].insertAdjacentHTML('afterend', '<p class="fc-hint">タップで裏面を表示</p>');

  // Nav bar before first card
  var nav = document.createElement('div');
  nav.className = 'fc-nav';
  nav.innerHTML =
    '<button id="fc-prev" disabled>← 前へ</button>' +
    '<span class="fc-counter" id="fc-count">1 / ' + cards.length + '</span>' +
    '<button id="fc-next">次へ →</button>';
  cards[0].parentNode.insertBefore(nav, cards[0]);

  function show(n) {
    cards[current].style.display = 'none';
    cards[current].classList.remove('flipped');
    current = n;
    cards[current].style.display = '';
    document.getElementById('fc-count').textContent = (current+1) + ' / ' + cards.length;
    document.getElementById('fc-prev').disabled = current === 0;
    document.getElementById('fc-next').disabled = current === cards.length - 1;
  }

  document.getElementById('fc-prev').addEventListener('click', function() {
    if (current > 0) show(current - 1);
  });
  document.getElementById('fc-next').addEventListener('click', function() {
    if (current < cards.length - 1) show(current + 1);
  });

})();
</script>
"""


def extract_canvas_css_links(html: str) -> str:
    """Extract Canvas CDN stylesheet <link> tags (public, no auth needed)."""
    links = re.findall(
        r'<link[^>]+(?:stylesheet|preload)[^>]+(?:cloudfront\.net|instructure-uploads)[^>]*/?>',
        html
    )
    return "\n".join(links)


def extract_body_and_title(html: str):
    """Extract WIKI_PAGE.body content and page title."""
    m = re.search(r'"body"\s*:\s*("(?:[^"\\]|\\.)*")', html)
    body = json.loads(m.group(1)) if m else ""

    m2 = re.search(r'"title"\s*:\s*"([^"]+)"', html)
    title = m2.group(1) if m2 else ""
    if not title:
        m3 = re.search(r'<title>(.*?)</title>', html)
        title = re.sub(r'<[^>]+>', '', m3.group(1)).strip() if m3 else "Untitled"
    return body, title


def get_title(html: str) -> str:
    _, title = extract_body_and_title(html)
    return title


def _normalize_module_name(name: str) -> str:
    name = re.sub(r'&amp;', 'and', name)
    name = re.sub(r',\s+and\b', ' and', name)
    name = re.sub(r'[–—]', '-', name)   # normalize em/en-dash to hyphen
    name = name.replace('\xa0', ' ')    # normalize non-breaking space
    name = re.sub(r'\s+', ' ', name).strip()
    # Normalize capitalization: title-case the part after "Module N: "
    m = re.match(r'(Module \d+:)\s*(.*)', name, re.IGNORECASE)
    if m:
        rest = m.group(2).strip().title()
        # Fix common title-case artifacts (prepositions/articles)
        for word in ('And', 'Of', 'The', 'For', 'In', 'A', 'An', 'With', 'To', 'At', 'By', 'From'):
            rest = re.sub(rf'\b{word}\b', word.lower(), rest)
        # Uppercase abbreviations in parentheses e.g. (Abs) -> (ABS)
        rest = re.sub(r'\(([^)]{1,6})\)', lambda x: '(' + x.group(1).upper() + ')', rest)
        # Ensure first character is uppercase
        rest = rest[0].upper() + rest[1:] if rest else rest
        name = m.group(1) + ' ' + rest
    return name


def _extract_module_num(filename: str):
    """Extract module number from lesson code, e.g. _101_ -> 1, _1001_ -> 10."""
    m = re.search(r'_items_\d+_(\d{3,4})_', filename)
    if not m:
        return None
    return int(m.group(1)) // 100


def _extract_info_from_header(html: str):
    """Extract (module_num, topic) from Japanese dp-header.
    e.g. 'モジュール1：固定利付証券の特徴（Fixed-Income Instrument Features）...' -> (1, 'Fixed-Income Instrument Features')
    """
    m = re.search(r'<header[^>]*class="dp-header[^"]*"[^>]*>(.*?)</header>', html, re.DOTALL)
    if not m:
        # Fallback: bare search for モジュールN in full HTML
        nm = re.search(r'モジュール(\d+)', html)
        return (int(nm.group(1)), None) if nm else (None, None)
    text = re.sub(r'<[^>]+>', ' ', m.group(1))
    nm = re.search(r'モジュール(\d+)', text)
    if not nm:
        return None, None
    module_num = int(nm.group(1))
    # Extract English topic from first （...） or (...) before ｜ separator
    before_pipe = text.split('｜')[0]
    topic_m = re.search(r'[（(]([^）)]{3,60})[）)]', before_pipe)
    topic = topic_m.group(1).strip() if topic_m else None
    return module_num, topic


def _extract_topic_from_wrapper_title(html: str):
    """Extract topic from dp-wrapper title like 'Learning Outcomes: Fixed-Income ...' -> 'Fixed-Income ...'"""
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

    # 1. Numeric lesson code in filename -> map lookup
    result = _map_lookup(_extract_module_num(filename))
    if result:
        return result

    # 2. dp-header-pre text -> map lookup or direct normalize
    m = re.search(r'<span class="dp-header-pre">([^<]+)</span>', html)
    if m:
        raw = m.group(1).strip()
        nm = re.match(r'Module\s+(\d+):', raw, re.IGNORECASE)
        if nm:
            result = _map_lookup(int(nm.group(1)))
            if result:
                return result
        return _normalize_module_name(raw)

    # 3. Japanese header -> map lookup, then build from topic sources
    mod_num, hdr_topic = _extract_info_from_header(html)
    if mod_num is not None:
        result = _map_lookup(mod_num)
        if result:
            return result
        topic = _extract_topic_from_wrapper_title(html) or hdr_topic
        if topic:
            return _normalize_module_name(f'Module {mod_num}: {topic}')
        return f'Module {mod_num}'

    return "General"


def get_course_name(filename: str) -> str:
    course_map = {
        '1864': 'Quantitative Methods',
        '1865': 'Economics',
        '1866': 'Financial Statement Analysis',
        '1867': 'Corporate Issuers',
        '1868': 'Equity Investments',
        '1869': 'Fixed Income',
        '1870': 'Derivatives',
        '1871': 'Alternative Investments',
        '1872': 'Portfolio Management',
        '1873': 'Ethical and Professional Standards',
    }
    m = re.search(r'courses_(\d+)_', filename)
    return course_map.get(m.group(1) if m else '', 'CFA L1') if m else 'CFA L1'


def build_clean_page(html: str, title: str, prev_name: str, next_name: str) -> str:
    """
    Build a clean HTML page with:
    - Canvas CDN CSS only (no Canvas JS that would clobber content)
    - WIKI_PAGE.body content
    - Our nav bar + interactive JS
    """
    canvas_css = extract_canvas_css_links(html)
    content, _ = extract_body_and_title(html)

    nav_bar = f"""<div id="viewer-nav">
  <a href="index.html">☰ Index</a>
  <a href="{prev_name}" {"" if prev_name else 'class="disabled"'}>← 前へ</a>
  <span class="title">{title}</span>
  <a href="{next_name}" {"" if next_name else 'class="disabled"'}>次へ →</a>
</div>"""

    # Make dt elements tappable on iOS Safari by adding onclick=""
    content = re.sub(r'<dt\b([^>]*class="[^"]*dp-qc-answer[^"]*"[^>]*)>',
                     r'<dt\1 onclick="">', content)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{canvas_css}
{NAV_CSS}
</head>
<body class="full-width-layout lti-student-view">
<div class="ic-app-nav-toggle-and-crumbs" style="display:none"></div>
<div id="main" style="margin:0;padding:0 16px 16px;">
  <div class="show-content user_content clearfix enhanced">
{content}
  </div>
</div>
{nav_bar}
{INTERACTIVE_JS}
</body>
</html>"""


def index_html(lessons: list) -> str:
    # Use plain dicts to preserve insertion order (= file order).
    # module_keys[course][module_key] = display_name  (dedup by lowercase key)
    courses: dict = {}       # course -> {module_key -> [items]}
    module_display: dict = {}  # course -> {module_key -> display_name}
    for l in lessons:
        course = l['course']
        mod_key = l['module'].lower()
        courses.setdefault(course, {}).setdefault(mod_key, []).append((l['name'], l['title']))
        module_display.setdefault(course, {}).setdefault(mod_key, l['module'])

    rows = ""
    for course, modules in courses.items():
        rows += f'<h2>{course}</h2>\n'
        for mod_key, items in modules.items():
            display = module_display[course][mod_key]
            rows += f'<h3>{display}</h3><ul>\n'
            for name, title in items:
                rows += f'<li><a href="{name}">{title}</a></li>\n'
            rows += '</ul>\n'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CFA Level 1</title>
<style>
body {{ font-family: sans-serif; max-width: 720px; margin: 0 auto; padding: 16px 20px 40px; color: #222; }}
h1 {{ font-size: 22px; color: #1a3a5c; border-bottom: 2px solid #0770a3; padding-bottom: 8px; }}
h2 {{ font-size: 17px; color: #0770a3; margin: 28px 0 6px; }}
h3 {{ font-size: 13px; color: #666; text-transform: uppercase; letter-spacing: .4px; margin: 16px 0 4px; }}
ul {{ margin: 0 0 8px 0; padding-left: 18px; }}
li {{ margin: 4px 0; }}
a {{ color: #0770a3; text-decoration: none; font-size: 14px; }}
a:hover {{ text-decoration: underline; }}
p {{ color: #888; font-size: 13px; }}
</style>
</head>
<body>
<h1>CFA Level 1 Curriculum</h1>
<p>{len(lessons)} lessons</p>
{rows}
</body>
</html>"""


def main():
    files = sorted([
        f for f in TRANSLATED_DIR.glob("courses_*_modules_items_*.html")
        if '{{' not in f.name
    ])
    print(f"Processing {len(files)} files...")

    # First pass: build (course_id, module_num) -> module_name
    # Read all HTML once and cache; build map from multiple sources
    html_cache: dict = {}
    for f in files:
        html_cache[f.name] = f.read_text(encoding="utf-8", errors="ignore")

    module_map: dict = {}
    for f in files:
        html = html_cache[f.name]
        course_m = re.search(r'courses_(\d+)_', f.name)
        if not course_m:
            continue
        course_id = course_m.group(1)

        # Priority 1: dp-header-pre + numeric filename code
        pre_m = re.search(r'<span class="dp-header-pre">([^<]+)</span>', html)
        mod_num_file = _extract_module_num(f.name)
        if pre_m and mod_num_file is not None:
            key = (course_id, mod_num_file)
            if key not in module_map:
                module_map[key] = _normalize_module_name(pre_m.group(1).strip())

        # Priority 2: Japanese header (module num + topic) OR dp-wrapper title topic
        mod_num_hdr, hdr_topic = _extract_info_from_header(html)
        title_topic = _extract_topic_from_wrapper_title(html)
        topic = title_topic or hdr_topic
        if mod_num_hdr is not None and topic:
            key = (course_id, mod_num_hdr)
            if key not in module_map:
                module_map[key] = _normalize_module_name(f'Module {mod_num_hdr}: {topic}')

    lessons = []
    for f in files:
        html = html_cache[f.name]
        title = get_title(html)
        lessons.append({
            'src': f,
            'name': f.name,
            'title': title,
            'course': get_course_name(f.name),
            'module': get_module_name(html, f.name, module_map),
            'html': html,
        })

    for i, lesson in enumerate(lessons):
        prev_name = lessons[i - 1]['name'] if i > 0 else ''
        next_name = lessons[i + 1]['name'] if i < len(lessons) - 1 else ''
        out_html = build_clean_page(lesson['html'], lesson['title'], prev_name, next_name)
        (OUT_DIR / lesson['name']).write_text(out_html, encoding='utf-8')
        print(f"  [{i+1}/{len(lessons)}] {lesson['title'][:65]}")

    (OUT_DIR / 'index.html').write_text(index_html(lessons), encoding='utf-8')

    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "YOUR_MAC_IP"

    print(f"\nDone. {len(lessons)} pages → {OUT_DIR}")


if __name__ == '__main__':
    main()
