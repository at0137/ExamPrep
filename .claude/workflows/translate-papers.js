export const meta = {
  name: 'translate-papers',
  description: '英語論文PDFを和訳(数式LaTeX/表図は原画像埋め込み)し単一HTML化する',
  phases: [
    { title: 'Render', detail: 'PDF→PNG (render_pdf.py)' },
    { title: 'Translate', detail: 'ページ範囲を並列翻訳(表図は自動でEMBEDマーカー)' },
    { title: 'Verify', detail: '数式・証明ページのLaTeX検算' },
    { title: 'Finalize', detail: 'embed_page_images --auto + build_paper_viewer' },
  ],
}

// args: 論文名(references/<name>.pdf)。配列 / JSON文字列 / 単一文字列のいずれも受ける
// (Workflowのargsは配列を渡してもJSON文字列化されて届く場合があるため正規化する)
let papers = args
if (typeof papers === 'string') {
  const s = papers.trim()
  if (s.startsWith('[')) { try { papers = JSON.parse(s) } catch (e) { papers = [s] } }
  else papers = [s]
}
if (!Array.isArray(papers)) papers = [papers]
papers = papers.filter(Boolean)
if (!papers.length) throw new Error('args に論文名(配列 or JSON文字列)を渡してください')

const ROOT = '/Users/tarai/Research/ExamPrep'
const CHUNK = 6

function ranges(total, size) {
  const out = []
  for (let s = 1; s <= total; s += size) out.push([s, Math.min(s + size - 1, total)])
  return out
}

const RULES = `各ページ pages_png/pNNN.png (NNNはゼロ詰め3桁) を Read で画像として読み、translated_md/NNN.md を Write する。既に NNN.md が存在すればskip。
判定と出力ルール:
- ページが主に「数値の詰まった表」または「図・チャート中心」なら転記しない。先頭行に <!--EMBED--> を置き、続けて見出し(表番号/図番号があれば)とキャプションの和訳だけを書く(数値・図は後段で原画像に差し替わる)。
- それ以外(散文・数式中心の本文)は通常翻訳: 自然な日本語(直訳調を避ける)、数式は $...$ / $$...$$ でLaTeX化、式番号は \\tag{...} で保持、見出しは # / ## / ###。
- 参考文献(References)ページは英語原文のまま転記。
- ページ番号・走りヘッダー・フッターの定型部分は出力しない。本文中の脚注内容は訳して残す。
- メジャーでない固有名詞・専門用語は和訳の右に (English) を併記し、論文内で訳語を統一する。
- ＄記号を書くときは $\\$$ のように書かない(偶発的に $$ を作り描画が壊れる)。素の「＄」を使う。
- 出力はMarkdown本体のみ。前置き・後置きは一切付けない。`

const PAGES_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: { pages: { type: 'integer' } }, required: ['pages'],
}
const FINAL_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: { ok: { type: 'boolean' }, note: { type: 'string' } },
  required: ['ok', 'note'],
}

const results = await pipeline(
  papers,

  // ── Render ──
  (paper) => agent(
    `作業ディレクトリは ${ROOT}。次を実行してPDFをページ画像に描画せよ:\n` +
    `python3 scripts/render_pdf.py --name "${paper}"\n` +
    `出力の "PAGES=<n>" の n を pages として返せ(失敗時は pages=0)。`,
    { label: `render:${paper.slice(0, 24)}`, phase: 'Render', effort: 'low', schema: PAGES_SCHEMA }
  ),

  // ── Translate (ページ範囲で並列, 自動判定) ──
  async (rendered, paper) => {
    const total = rendered && rendered.pages ? rendered.pages : 0
    if (!total) throw new Error(`render失敗: ${paper}`)
    const base = `${ROOT}/Papers/${paper}`
    const rs = ranges(total, CHUNK)
    await parallel(rs.map(([a, b]) => () => agent(
      `英語学術論文「${paper}」のページ画像を和訳Markdownに変換するタスク。\n` +
      `作業ディレクトリ(絶対パス): ${base}\n担当ページ: ${a}〜${b}\n` +
      `この論文は全${total}ページ。ファイル番号はこの論文内で1始まり(ページN→translated_md/NNN.md)。` +
      `担当範囲外・${total}を超える番号のファイルは絶対に作らない。\n\n${RULES}\n\n` +
      `完了したら書き出したファイルと各ページの種別(本文/数式/表→EMBED/図→EMBED/参考文献)を1行ずつ報告せよ。`,
      { label: `tr:${paper.slice(0, 14)}:${a}-${b}`, phase: 'Translate' }
    )))
    return { paper, total }
  },

  // ── Verify (数式・証明ページのLaTeX検算) ──
  async ({ paper, total }) => {
    const base = `${ROOT}/Papers/${paper}`
    await agent(
      `論文「${paper}」の和訳の数式を検証・修正するタスク。\n作業ディレクトリ(絶対パス): ${base}\n` +
      `手順:\n1. translated_md/*.md のうち $$ や \\tag や「証明/Proof/命題」を含む数式中心ページを特定する。\n` +
      `2. 各該当ページについて pages_png/pNNN.png を Read し md と突き合わせ、数式の構造(分数・添字・上付き下付き・総和・行列・転置)とLaTeX妥当性($..$/$$..$$の対応、コマンド綴り)、式番号(\\tag)の一致を厳密に確認する。\n` +
      `3. 誤り・崩れは Edit で直接修正する。判読不能で確証が持てない式は勝手に創作せず、その式直後に <!-- 要確認: 原画像が不鮮明 --> を付す。\n` +
      `<!--EMBED--> マーカー付きの表・図ページは対象外(後段で画像化される)。\n` +
      `ページごとに「修正なし」または修正点を簡潔に報告せよ。`,
      { label: `vrf:${paper.slice(0, 18)}`, phase: 'Verify', effort: 'high' }
    )
    return { paper, total }
  },

  // ── Finalize (連番検証 → 画像埋め込み + 単一HTMLビルド) ──
  ({ paper, total }) => agent(
    `作業ディレクトリは ${ROOT}。論文「${paper}」(全${total}ページ)を仕上げる。\n` +
    `1. まず translated_md/ に 001.md〜${String(total).padStart(3, '0')}.md が連番で揃っているか確認し、` +
    `欠落や${total}超の余分ファイルがあれば note に列挙する(欠落ページは pages_png/pNNN.png を読んで翻訳し補完してよい)。\n` +
    `2. 次の2コマンドを順に実行:\n` +
    `python3 scripts/embed_page_images.py --name "${paper}" --auto\n` +
    `python3 scripts/build_paper_viewer.py --name "${paper}"\n` +
    `両方成功なら ok=true、note に「連番OK/欠落補完N / 埋め込みN / 連結M」等の要点。エラー時は ok=false で note にエラー全文。`,
    { label: `fin:${paper.slice(0, 22)}`, phase: 'Finalize', effort: 'low', schema: FINAL_SCHEMA }
  ),
)

return results.filter(Boolean)
