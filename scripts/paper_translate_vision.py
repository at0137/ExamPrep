"""
paper_translate_vision.py — 英語論文PDFを「ページ画像 → ChatGPT Vision」で
日本語Markdown(+LaTeX)に変換するパイプライン（方式A）。

処理の流れ:
  1. PDF を 1ページ = 1枚の PNG に変換 (PyMuPDF)
  2. 各ページ画像を ChatGPT に添付し、転記+和訳+LaTeX化した Markdown を取得
  3. Papers/<slug>/translated_md/NNN.md として保存（ページ単位・レジューム対応）

その後 build_paper_viewer.py で HTML 化すると dist/Papers/<slug>/ に公開用が出る。

使い方:
    # 1. 別ターミナルでデバッグポート付き Chrome を起動し ChatGPT にログイン
    #    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
    # 2. 変換実行（原本PDFは references/ に置く。--pdf はファイル名だけでも可）
    python3 scripts/paper_translate_vision.py \
        --pdf frazzini_pedersen_2014_bab.pdf \
        --name "[2010] Betting Against Beta (Frazzini, Pedersen)"
    # ページ範囲指定 / DPI指定:
    #   --pages 8-12   --dpi 200

命名規則:
    --name は "[YYYY] 英文Title (Author)" 形式。これがそのまま
    Papers/<name>/ と dist/Papers/<name>/ のフォルダ名になる。

オプション:
    --pages A-B   指定ページ範囲のみ（1始まり、両端含む）
    --no-resume   既存の翻訳済みページも再変換
"""

import argparse
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF

sys.path.insert(0, str(Path(__file__).parent))
from chatgpt_translator import ChatGPTTranslator

_ROOT = Path(__file__).parent.parent


def _parse_pages(spec: str, total: int):
    """'8-12' / '5' を 0始まりインデックスのリストに。未指定なら全ページ。"""
    if not spec:
        return list(range(total))
    if "-" in spec:
        a, b = spec.split("-", 1)
        start, end = int(a), int(b)
    else:
        start = end = int(spec)
    start = max(1, start)
    end = min(total, end)
    return list(range(start - 1, end))


def render_pages(pdf_path: Path, png_dir: Path, dpi: int, pages: list):
    """指定ページを PNG 化。既存はスキップ。ファイルパスのリストを返す。"""
    png_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    out = []
    for i in pages:
        png = png_dir / f"p{i+1:03d}.png"
        if not png.exists():
            doc[i].get_pixmap(dpi=dpi).save(str(png))
        out.append((i + 1, png))
    doc.close()
    return out


def _resolve_pdf(pdf_arg: str) -> Path:
    """--pdf をそのまま、無ければ references/ 配下として解決する。"""
    p = Path(pdf_arg)
    if p.exists():
        return p
    cand = _ROOT / "references" / pdf_arg
    if cand.exists():
        return cand
    raise SystemExit(f"PDFが見つかりません: {pdf_arg}（references/ にも無し）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True,
                    help="論文PDF。パス or references/ 配下のファイル名")
    ap.add_argument("--name", required=True,
                    help='論文名 "[YYYY] 英文Title (Author)"。'
                         '出力先 Papers/<name> / dist/Papers/<name>')
    ap.add_argument("--pages", default="", help="ページ範囲 例: 8-12 (1始まり)")
    ap.add_argument("--dpi", type=int, default=170, help="ページ画像のDPI")
    ap.add_argument("--resume", action="store_true", default=True,
                    help="翻訳済みページをスキップ（既定: on）")
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    args = ap.parse_args()

    pdf_path = _resolve_pdf(args.pdf)
    base = _ROOT / "Papers" / args.name
    png_dir = base / "pages_png"
    md_dir = base / "translated_md"
    md_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    total = len(doc)
    doc.close()
    page_idx = _parse_pages(args.pages, total)
    print(f"PDF {pdf_path.name}: {total} pages, 処理対象 {len(page_idx)} ページ")

    rendered = render_pages(pdf_path, png_dir, args.dpi, page_idx)
    print(f"ページ画像 {len(rendered)} 枚 → {png_dir}")

    with ChatGPTTranslator(reset_every=8) as tr:
        for pno, png in rendered:
            out_md = md_dir / f"{pno:03d}.md"
            if args.resume and out_md.exists():
                print(f"  [skip] p{pno}")
                continue
            print(f"  p{pno} を Vision 変換中...")
            md = None
            for attempt in range(3):
                try:
                    md = tr.translate_image(png)
                    if md and len(md.strip()) > 10:
                        break
                    print(f"    空応答、リトライ {attempt+1}")
                except Exception as e:
                    print(f"    エラー: {e} リトライ {attempt+1}")
                    time.sleep(5)
            if not md:
                print(f"  ! p{pno} 失敗、保存せずスキップ")
                continue
            # 先頭にページ見出しを付けて結合時に区切りが分かるように
            out_md.write_text(md.strip() + "\n", encoding="utf-8")
            print(f"  ✓ p{pno} → {out_md.name}")
            time.sleep(2)

    print(f'\nDone. 次に: python3 scripts/build_paper_viewer.py --name "{args.name}"')


if __name__ == "__main__":
    main()
