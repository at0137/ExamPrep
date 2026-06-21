"""
render_pdf.py — 論文PDFを 1ページ=1枚の PNG に描画する（PyMuPDF）。

翻訳パイプラインの決定論パート①。references/<name>.pdf を
Papers/<name>/pages_png/pNNN.png に描画する（既存はスキップ＝レジューム）。

使い方:
    python3 scripts/render_pdf.py --name "[1987] ... (Newey, West)"
    # DPI 指定: --dpi 200 / 強制再描画: --force
出力末尾に "PAGES=<総ページ数>" を1行出すので、呼び出し側がページ数を取れる。
"""

import argparse
from pathlib import Path

import fitz  # PyMuPDF

_ROOT = Path(__file__).parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help='論文名 "[YYYY] Title (Author)"')
    ap.add_argument("--dpi", type=int, default=170)
    ap.add_argument("--force", action="store_true", help="既存PNGも再描画")
    args = ap.parse_args()

    pdf = _ROOT / "references" / f"{args.name}.pdf"
    if not pdf.exists():
        raise SystemExit(f"PDFが見つかりません: {pdf}")

    png_dir = _ROOT / "Papers" / args.name / "pages_png"
    png_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf)
    total = len(doc)
    made = 0
    for i in range(total):
        out = png_dir / f"p{i+1:03d}.png"
        if out.exists() and not args.force:
            continue
        doc[i].get_pixmap(dpi=args.dpi).save(str(out))
        made += 1
    doc.close()

    print(f"{pdf.name}: {total} ページ中 {made} 枚を描画 → {png_dir}")
    print(f"PAGES={total}")


if __name__ == "__main__":
    main()
