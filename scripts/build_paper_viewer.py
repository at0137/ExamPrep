"""
build_paper_viewer.py — Markdown(+LaTeX) の論文和訳を MathJax 付き HTML にして
dist/Papers/<name>/ に出力する。

<name> は命名規則 "[YYYY] 英文Title (Author)" を想定（例:
"[2010] Betting Against Beta (Frazzini, Pedersen)"）。

入力: Papers/<name>/translated_md/*.md  (本文に $...$ / $$...$$ の LaTeX 数式を含む Markdown)
出力: dist/Papers/<name>/*.html  + index.html

Markdown は marked.js でクライアント側レンダリング、数式は MathJax v3 で描画する。
サーバ側に markdown ライブラリを入れる必要がない（= Python 3.8 でも動く）。

使い方:
    python3 scripts/build_paper_viewer.py --name "[2010] Betting Against Beta (Frazzini, Pedersen)"
"""

import argparse
import html
import re
from pathlib import Path
from urllib.parse import quote

_ROOT = Path(__file__).parent.parent


def _title_from_md(md: str, fallback: str) -> str:
    # 1) Markdown 見出し (# ...) を最優先
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # 2) 無ければ最初の非空行をタイトル扱い（記号を除去し長すぎたら切り詰め）
    for line in md.splitlines():
        s = re.sub(r"^[#>\-\*\s]+", "", line).strip()
        if len(s) >= 2:
            return s[:60] + ("…" if len(s) > 60 else "")
    return fallback


PAGE_TMPL = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script>
  window.MathJax = {{
    tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
            displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']] }},
    options: {{ skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] }}
  }};
</script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" id="MathJax-script" async></script>
<style>
  body {{ font-family: -apple-system, "Hiragino Kaku Gothic ProN", sans-serif;
         max-width: 760px; margin: 0 auto; padding: 16px 20px 72px;
         color: #1a1a1a; line-height: 1.85; font-size: 16px; }}
  h1 {{ font-size: 22px; color: #1a3a5c; border-bottom: 2px solid #0770a3; padding-bottom: 8px; }}
  h2 {{ font-size: 19px; color: #0770a3; margin-top: 32px; }}
  h3 {{ font-size: 16px; color: #444; }}
  table {{ border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 10px; }}
  img {{ max-width: 100%; }}
  mjx-container[display="true"] {{ overflow-x: auto; overflow-y: hidden; }}
  figure {{ margin: 16px 0; text-align: center; }}
  figcaption {{ font-size: 13px; color: #666; }}
  #nav {{ position: fixed; bottom: 0; left: 0; right: 0; z-index: 999;
          background: rgba(30,50,70,.94); display: flex; justify-content: space-between;
          align-items: center; padding: 8px 14px; gap: 8px; font-size: 13px; }}
  #nav a {{ color: #fff; text-decoration: none; background: rgba(255,255,255,.15);
            border-radius: 5px; padding: 6px 14px; white-space: nowrap; }}
  #nav a.disabled {{ opacity: .3; pointer-events: none; }}
  #nav .t {{ color: #cde; flex: 1; text-align: center; overflow: hidden;
             text-overflow: ellipsis; white-space: nowrap; }}
</style>
</head>
<body>
<div id="content"></div>
<div id="nav">
  <a href="index.html">☰ 目次</a>
  <a href="{prev}" {prev_dis}>← 前へ</a>
  <span class="t">{title}</span>
  <a href="{next}" {next_dis}>次へ →</a>
</div>
<script type="text/markdown" id="src">{md}</script>
<script>
  (function () {{
    var src = document.getElementById('src').textContent;
    var store = [];
    function keep(m) {{ store.push(m); return '@@MJX' + (store.length - 1) + '@@'; }}
    // marked が数式内の _ * \\ を壊さないよう、変換前に数式を退避する
    src = src.replace(/\\$\\$[\\s\\S]+?\\$\\$/g, keep)   // $$...$$
             .replace(/\\\\\\[[\\s\\S]+?\\\\\\]/g, keep) // \\[...\\]
             .replace(/\\\\\\([\\s\\S]+?\\\\\\)/g, keep) // \\(...\\)
             .replace(/\\$(?:\\\\.|[^\\$\\n])+?\\$/g, keep); // $...$ (1行内)
    var out = marked.parse(src);
    out = out.replace(/@@MJX(\\d+)@@/g, function (_, i) {{ return store[+i]; }});
    document.getElementById('content').innerHTML = out;
    if (window.MathJax && MathJax.typesetPromise) {{ MathJax.typesetPromise(); }}
  }})();
</script>
</body>
</html>"""


def build_page(md: str, title: str, prev: str, next_: str) -> str:
    # md は textContent として読むので </script> だけ無害化すれば十分
    safe_md = md.replace("</script>", "<\\/script>")
    return PAGE_TMPL.format(
        title=html.escape(title),
        md=safe_md,
        prev=prev, next=next_,
        prev_dis="" if prev else 'class="disabled"',
        next_dis="" if next_ else 'class="disabled"',
    )


SINGLE_TMPL = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script>
  window.MathJax = {{
    tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
            displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']] }},
    options: {{ skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] }}
  }};
</script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" id="MathJax-script" async></script>
<style>
  body {{ font-family: -apple-system, "Hiragino Kaku Gothic ProN", sans-serif;
         max-width: 820px; margin: 0 auto; padding: 16px 20px 64px;
         color: #1a1a1a; line-height: 1.85; font-size: 16px; }}
  h1 {{ font-size: 22px; color: #1a3a5c; border-bottom: 2px solid #0770a3; padding-bottom: 8px; }}
  h2 {{ font-size: 19px; color: #0770a3; margin-top: 32px; }}
  h3 {{ font-size: 16px; color: #444; }}
  table {{ border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 10px; }}
  img {{ max-width: 100%; }}
  mjx-container[display="true"] {{ overflow-x: auto; overflow-y: hidden; }}
  figure {{ margin: 16px 0; text-align: center; }}
  figcaption {{ font-size: 13px; color: #666; }}
  .pagemark {{ margin: 40px 0 4px; padding-top: 16px; border-top: 1px dashed #cfd8e0;
               color: #9aa7b2; font-size: 12px; letter-spacing: .08em; }}
  .topbar {{ font-size: 13px; margin-bottom: 8px; }}
  .topbar a {{ color: #0770a3; text-decoration: none; }}
</style>
</head>
<body>
<div class="topbar"><a href="../index.html">☰ 論文一覧</a></div>
<div id="content"></div>
<script type="text/markdown" id="src">{md}</script>
<script>
  (function () {{
    var src = document.getElementById('src').textContent;
    var store = [];
    function keep(m) {{ store.push(m); return '@@MJX' + (store.length - 1) + '@@'; }}
    // marked が数式内の _ * \\ を壊さないよう、変換前に数式を退避する
    src = src.replace(/\\$\\$[\\s\\S]+?\\$\\$/g, keep)   // $$...$$
             .replace(/\\\\\\[[\\s\\S]+?\\\\\\]/g, keep) // \\[...\\]
             .replace(/\\\\\\([\\s\\S]+?\\\\\\)/g, keep) // \\(...\\)
             .replace(/\\$(?:\\\\.|[^\\$\\n])+?\\$/g, keep); // $...$ (1行内)
    var out = marked.parse(src);
    out = out.replace(/@@MJX(\\d+)@@/g, function (_, i) {{ return store[+i]; }});
    document.getElementById('content').innerHTML = out;
    if (window.MathJax && MathJax.typesetPromise) {{ MathJax.typesetPromise(); }}
  }})();
</script>
</body>
</html>"""


def build_single(pages: list, title: str) -> str:
    """pages: [(stem, md), ...] を1つの連続HTMLに連結する。"""
    chunks = []
    for stem, md in pages:
        chunks.append(f'<div class="pagemark">p.{stem}</div>\n\n{md.strip()}')
    combined = "\n\n".join(chunks)
    safe_md = combined.replace("</script>", "<\\/script>")
    return SINGLE_TMPL.format(title=html.escape(title), md=safe_md)


def index_page(slug: str, items: list) -> str:
    lis = "\n".join(
        f'<li><a href="{name}">{html.escape(title)}</a></li>'
        for name, title in items
    )
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(slug)} — 論文和訳</title>
<style>
 body {{ font-family: sans-serif; max-width: 720px; margin: 0 auto; padding: 20px; }}
 h1 {{ font-size: 22px; color: #1a3a5c; border-bottom: 2px solid #0770a3; padding-bottom: 8px; }}
 li {{ margin: 6px 0; }} a {{ color: #0770a3; text-decoration: none; }}
</style></head><body>
<h1>{html.escape(slug)}</h1>
<ul>{lis}</ul>
</body></html>"""


def rebuild_papers_index():
    """dist/Papers/index.html を全論文スラッグから再生成。各論文の最初の.mdのH1を表題に。"""
    papers_root = _ROOT / "dist" / "Papers"
    rows = []
    for d in sorted(p for p in papers_root.iterdir() if p.is_dir()):
        md_dir = _ROOT / "Papers" / d.name / "translated_md"
        title = d.name
        mds = sorted(md_dir.glob("*.md")) if md_dir.exists() else []
        if mds:
            title = _title_from_md(mds[0].read_text(encoding="utf-8"), d.name)
        href = quote(d.name) + "/index.html"
        rows.append(f'<li><a href="{href}">{html.escape(title)}</a></li>')
    body = "\n".join(rows) or "<li>（まだ論文がありません）</li>"
    (papers_root / "index.html").write_text(f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>論文和訳ライブラリ</title>
<style>
 body {{ font-family: sans-serif; max-width: 720px; margin: 0 auto; padding: 24px 20px; }}
 h1 {{ font-size: 22px; color: #1a3a5c; border-bottom: 2px solid #0770a3; padding-bottom: 8px; }}
 li {{ margin: 8px 0; }} a {{ color: #0770a3; text-decoration: none; font-size: 16px; }}
</style></head><body>
<h1>📄 論文和訳ライブラリ</h1>
<ul>{body}</ul>
</body></html>""", encoding="utf-8")
    print(f"  papers index → {papers_root/'index.html'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True,
                    help='論文名 "[YYYY] 英文Title (Author)"。'
                         'Papers/<name>/ と dist/Papers/<name>/ に対応')
    ap.add_argument("--in-dir", default=None,
                    help="Markdown 入力ディレクトリ (既定: Papers/<name>/translated_md)")
    ap.add_argument("--paged", action="store_true",
                    help="ページごとに別HTML＋目次リンク集を出す（旧挙動）。"
                         "既定は全ページを1つの連続HTMLにまとめる")
    args = ap.parse_args()

    in_dir = Path(args.in_dir) if args.in_dir \
        else _ROOT / "Papers" / args.name / "translated_md"
    out_dir = _ROOT / "dist" / "Papers" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("*.md"))
    if not files:
        print(f"no .md files in {in_dir}")
        return

    parsed = []
    for f in files:
        md = f.read_text(encoding="utf-8")
        parsed.append((f.stem, _title_from_md(md, f.stem), md))

    if args.paged:
        for i, (stem, title, md) in enumerate(parsed):
            prev = parsed[i - 1][0] + ".html" if i > 0 else ""
            next_ = parsed[i + 1][0] + ".html" if i < len(parsed) - 1 else ""
            (out_dir / (stem + ".html")).write_text(
                build_page(md, title, prev, next_), encoding="utf-8")
            print(f"  [{i+1}/{len(parsed)}] {title[:60]}")
        (out_dir / "index.html").write_text(
            index_page(args.name, [(s + ".html", t) for s, t, _ in parsed]),
            encoding="utf-8")
    else:
        # 既定: 全ページを1つの連続HTMLに。旧来の分割HTMLが残っていれば掃除する
        for old in out_dir.glob("[0-9]*.html"):
            old.unlink()
        (out_dir / "index.html").write_text(
            build_single([(s, md) for s, _, md in parsed], args.name),
            encoding="utf-8")
        print(f"  単一HTML: {len(parsed)} ページを index.html に連結")

    rebuild_papers_index()
    print(f"\nDone → {out_dir}")


if __name__ == "__main__":
    main()
