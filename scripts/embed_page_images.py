"""
embed_page_images.py — 表・図など「数値転記が不正確になりやすいページ」を、
原ページ画像(base64データURI)＋和訳キャプションに置き換える。

数値の多い表をVisionで転記すると列ズレ・桁誤りが避けられない。これらのページは
原画像をそのまま見せ、見出し・キャプションだけ和訳で添える方が正確かつ有用。

処理:
  対象ページの translated_md/NNN.md について
    - Markdown表ブロック（| ... | 行）を除去（壊れた転記を捨てる）
    - 図プレースホルダ `![...](figure)` を実画像に差し替え
    - OCR不確実性の注記行（"注：原画像..." 等）を除去
    - 見出し・キャプション本文は残す
    - 末尾（または図プレースホルダ位置）に原ページ画像を base64 データURIで埋め込む
  画像は鮮明さ重視でグレースケール指定DPIで再レンダリング（PyMuPDF）。

使い方:
    python3 scripts/embed_page_images.py \
        --name "[2014] Betting Against Beta (Frazzini, Pedersen)" \
        --pages 42-71 --dpi 200
"""

import argparse
import base64
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

_ROOT = Path(__file__).parent.parent

_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_FIG_PLACEHOLDER = re.compile(r"^\s*!\[[^\]]*\]\(figure\)\s*$")
_OCR_NOTE = re.compile(r"^\s*注[：:]")
# 翻訳エージェントが「このページは表・図なので画像埋め込みにせよ」と付けるマーカー
_EMBED_MARKER = re.compile(r"<!--\s*EMBED\s*-->")


def _parse_pages(spec: str):
    """'42-71' / '58' を 1始まりのページ番号リストに。"""
    if "-" in spec:
        a, b = spec.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(spec)]


def _resolve_pdf(name: str) -> Path:
    cand = _ROOT / "references" / f"{name}.pdf"
    if cand.exists():
        return cand
    raise SystemExit(f"PDFが見つかりません: references/{name}.pdf")


def render_gray_png(doc, page_no: int, dpi: int) -> bytes:
    """1始まりページ番号をグレースケールPNGバイト列に。"""
    pix = doc[page_no - 1].get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    return pix.tobytes("png")


def to_data_uri(png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def strip_and_embed(md: str, data_uri: str) -> str:
    """表行・OCR注記を除去し、図プレースホルダ or 末尾に画像を埋め込む。"""
    img_md = f"![原ページ（原文の表・図）]({data_uri})"

    out = []
    placed = False
    for line in md.splitlines():
        if _EMBED_MARKER.search(line) and not line.strip().startswith("!["):
            continue                  # 制御用マーカー行は捨てる
        if _FIG_PLACEHOLDER.match(line):
            out.append(img_md)        # 図プレースホルダを実画像に差し替え
            placed = True
            continue
        if _TABLE_ROW.match(line):
            continue                  # 壊れた転記表を捨てる
        if _OCR_NOTE.match(line):
            continue                  # OCR不確実性の注記を捨てる
        out.append(line)

    # 連続する空行を1つに畳む
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not placed:
        text += "\n\n" + img_md       # 表ページは末尾に画像を付与
    return text + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--pages", help="対象ページ範囲 例 42-71 (1始まり)")
    ap.add_argument("--auto", action="store_true",
                    help="<!--EMBED--> マーカーを含む .md を自動検出して対象にする")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    if not args.pages and not args.auto:
        raise SystemExit("--pages か --auto のどちらかを指定してください")

    md_dir = _ROOT / "Papers" / args.name / "translated_md"
    if not md_dir.exists():
        raise SystemExit(f"見つかりません: {md_dir}")

    pdf_path = _resolve_pdf(args.name)
    doc = fitz.open(pdf_path)

    # translated_md は複数論文を通し番号で振っている場合があり（例 015.md..）、
    # 各PDFは1始まり。最小 md 番号を 1ページ目とみなしてオフセットを求める。
    all_stems = sorted(int(f.stem) for f in md_dir.glob("[0-9]*.md"))
    offset = (all_stems[0] - 1) if all_stems else 0

    if args.auto:
        pages = sorted(
            int(f.stem) for f in md_dir.glob("[0-9]*.md")
            if _EMBED_MARKER.search(f.read_text(encoding="utf-8"))
        )
        print(f"--auto: マーカー付き {len(pages)} ページを検出")
    else:
        pages = _parse_pages(args.pages)
    print(f"{pdf_path.name}: {len(pages)} ページを画像埋め込みに変換 (dpi={args.dpi})")

    done = 0
    for pno in pages:
        md_file = md_dir / f"{pno:03d}.md"
        if not md_file.exists():
            print(f"  [skip] {pno:03d}.md なし")
            continue
        png = render_gray_png(doc, pno - offset, args.dpi)
        new_md = strip_and_embed(md_file.read_text(encoding="utf-8"), to_data_uri(png))
        md_file.write_text(new_md, encoding="utf-8")
        print(f"  ✓ {pno:03d}.md ← 画像 {len(png)//1024}KB 埋め込み")
        done += 1

    doc.close()
    print(f"\nDone. {done} ページを変換。"
          f'次に: python3 scripts/build_paper_viewer.py --name "{args.name}"')


if __name__ == "__main__":
    main()
