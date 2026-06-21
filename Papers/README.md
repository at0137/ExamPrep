# 論文翻訳 → HTML化 → GitHub Pages 公開

英語の学術論文PDFを日本語に翻訳し、数式を MathJax できれいに表示する
HTMLにして、既存の CFA/CIPM サイトと同じ GitHub Pages で公開する仕組み。

## 方式C：Claudeエージェント直接翻訳 + Workflow（現行・推奨）

ChatGPTブラウザ自動操作(方式A)は不安定・逐次で遅い。現行はClaude本体/サブ
エージェントが **ページ画像を直接読んで翻訳** し、ページ範囲で並列化する。
数値の詰まった表・図ページは（転記すると列ズレ・桁誤りが避けられないので）
**原ページ画像を埋め込み、見出し・キャプションだけ和訳する**。全ページは
1つの連続HTMLに連結する。

### 再現手順（Claude Codeセッション内）

```
# 1. references/ に <name>.pdf を置く（命名規則は下記）
# 2. Workflow を名前で実行（描画→並列翻訳→数式検算→画像埋め込み→HTML を自動）
#    Claude に: 「translate-papers ワークフローを args=[論文名,...] で回して」
#    （.claude/workflows/translate-papers.js）
```

Workflow が各論文について次を行う:
`render_pdf.py`(PDF→PNG) → ページ範囲をサブエージェント並列翻訳（**表・図は
自動で `<!--EMBED-->` マーカーを付与**）→ 数式・証明ページのLaTeX検算 →
`embed_page_images.py --auto`（マーカー付きページを原画像に置換）→
`build_paper_viewer.py`（単一HTML化）。

### 個別スクリプト（手動でも実行可）

| スクリプト | 役割 |
|---|---|
| `scripts/render_pdf.py --name <name>` | PDF→ページPNG（決定論・レジューム） |
| `scripts/embed_page_images.py --name <name> --auto` | `<!--EMBED-->`付きページを原画像(base64)＋和訳キャプションに置換。`--pages A-B`で範囲指定も可 |
| `scripts/build_paper_viewer.py --name <name>` | 全ページを1つの `index.html` に連結（数式はmarked保護→MathJax描画）。`--paged`で旧来のページ分割 |

> 注意: ビューアは marked / MathJax を CDN から読み**ブラウザ側で描画**する。
> オフラインだと真っ白になる。数式は marked が壊さないよう保護してある。
> 翻訳時、＄記号は `$\$$` のように書かない（`$$`を偶発生成して描画が壊れる）。

## 方式：ChatGPT Vision（方式A・旧）

PDFを1ページずつ画像化し、ChatGPT に画像を渡して「転記 + 和訳 + LaTeX化」を
一発で行う。数式の再現精度が高く、追加インストールが不要（既存のブラウザ
ChatGPT エンジンをそのまま流用）。不安定・逐次のため現在は方式Cに移行。

> marker（方式B）も比較検証したが、この環境では依存が脆く（opencv の
> ソースビルド・transformers のバージョン衝突）、CPU 推論での数式OCR精度も
> 方式Aに劣ったため不採用。表・図が非常に多い論文を扱うときの補助として
> `.venv-marker` と `scripts/translate_md.py` を残してある。

## 命名規則

論文名 `<name>` は **`[YYYY] 英文Title (Author)`** 形式で統一する。
例: `[2010] Betting Against Beta (Frazzini, Pedersen)`
この名前がそのまま `references/<name>.pdf`・`Papers/<name>/`・`dist/Papers/<name>/`
のフォルダ／ファイル名になる。

## ディレクトリ構成

```
references/
  <name>.pdf         原本PDF（gitignore：著作物・大容量。ローカル保持）
Papers/
  <name>/
    pages_png/       ページ画像          （gitignore：再生成可能）
    translated_md/   和訳Markdown(+LaTeX) ★これが元データ（git追跡）
  README.md
dist/Papers/
  index.html         論文一覧
  <name>/            公開用HTML（MathJax付き）★git追跡 → Pages で公開
```

## 使い方

### 1. ChatGPT にログインしたデバッグ用 Chrome を起動

別ターミナルで（`!`プレフィックスでこのセッションからも可）：

```
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

開いた Chrome で ChatGPT に普通にログインしておく。

### 2. PDF を和訳（ページ画像 → Vision → Markdown）

原本PDFを `references/` に置き（ファイル名は `<name>.pdf` 推奨）、実行する。
`--pdf` はパスでも `references/` 配下のファイル名でも可。

```
python3 scripts/paper_translate_vision.py \
    --pdf "[2010] Betting Against Beta (Frazzini, Pedersen).pdf" \
    --name "[2010] Betting Against Beta (Frazzini, Pedersen)"
# 一部ページだけ:   --pages 8-12
# 画質を上げる:     --dpi 200
```

`Papers/<name>/translated_md/NNN.md` がページ単位で出力される（レジューム対応：
途中で止めても再実行で続きから）。誤訳・数式の崩れはこの .md を直接編集して直す。

### 3. HTML化（MathJax付き・ナビ・目次を生成）

```
python3 scripts/build_paper_viewer.py --name "[2010] Betting Against Beta (Frazzini, Pedersen)"
```

`dist/Papers/<name>/*.html` と一覧 `dist/Papers/index.html` が生成される。

### 4. ローカル確認

```
cd "dist/Papers/[2010] Betting Against Beta (Frazzini, Pedersen)" && python3 -m http.server 8080
# → http://localhost:8080
```

### 5. 公開

`main` に push すると `.github/workflows/deploy.yml` が `dist/` を GitHub Pages へ
自動デプロイする。論文は `https://<pages-url>/Papers/` 配下に並ぶ。

## スクリプト

| スクリプト | 役割 |
|---|---|
| `scripts/paper_translate_vision.py` | PDF→画像→ChatGPT Vision→和訳Markdown（方式A本体） |
| `scripts/build_paper_viewer.py` | Markdown(+LaTeX)→MathJax付きHTML + 目次/ナビ |
| `scripts/chatgpt_translator.py` | ブラウザ ChatGPT 操作エンジン（`translate_image` を追加済み） |
| `scripts/translate_md.py` | （方式B用）既存Markdownを数式保持のまま和訳 |
