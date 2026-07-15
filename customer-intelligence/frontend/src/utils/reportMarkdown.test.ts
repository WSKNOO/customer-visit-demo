import assert from 'node:assert/strict'
import { Marked } from 'marked'
import { compactHeadingId, normalizeReportMarkdown, parseReportHeadings } from './reportMarkdown'

const wrapped = `好的，我来为您整理报告。\r\n\r\n\`\`\`markdown
# 长鑫科技 客户拜访情报简报

## 目录

- [一、客户基本画像](#一客户基本画像)

## 一、客户基本画像

### 企业性质

正文
\`\`\``

const normalized = normalizeReportMarkdown(wrapped)
assert.ok(normalized.startsWith('# 长鑫科技'))
assert.ok(!normalized.includes('好的，我来为您整理报告'))
assert.ok(!normalized.includes('\`\`\`markdown'))
const wrappedHeadings = parseReportHeadings(normalized)
assert.deepEqual(wrappedHeadings.map(item => item.id), [
  '长鑫科技客户拜访情报简报', '目录', '一客户基本画像', '企业性质',
])
const html = new Marked({ gfm: true }).parse(normalized) as string
assert.ok(html.includes('<h1>长鑫科技 客户拜访情报简报</h1>'))
assert.ok(html.includes('<h2>一、客户基本画像</h2>'))
assert.ok(html.includes('<h3>企业性质</h3>'))
assert.ok(!html.includes('<pre><code class="language-markdown">'))

const multiple = `说明文字
\`\`\`md
## 一、客户基本画像

第一部分
\`\`\`
模块间说明
\`\`\`markdown
## 二、近期重点动态

第二部分
\`\`\``
assert.equal(
  normalizeReportMarkdown(multiple),
  '## 一、客户基本画像\n\n第一部分\n\n## 二、近期重点动态\n\n第二部分',
)

const realCode = `# 报告

## 接口示例

\`\`\`json
{"success": true}
\`\`\`

\`\`\`python
print("ok")
\`\`\``
const normalizedCode = normalizeReportMarkdown(realCode)
assert.ok(normalizedCode.includes('\`\`\`json'))
assert.ok(normalizedCode.includes('\`\`\`python'))
assert.deepEqual(parseReportHeadings(normalizedCode).map(item => item.text), ['报告', '接口示例'])

const unlabeledCode = `# 正常报告

## 普通代码示例

\`\`\`
# 这是代码中的注释
## 这不是报告标题
\`\`\``
assert.equal(normalizeReportMarkdown(unlabeledCode), unlabeledCode)
assert.deepEqual(parseReportHeadings(unlabeledCode).map(item => item.text), ['正常报告', '普通代码示例'])

const duplicates = parseReportHeadings(`# 2026年规划/方案
## 一、客户基本画像
## 一、客户基本画像
## 一、客户基本画像`)
assert.equal(compactHeadingId('2026年规划/方案'), '2026年规划方案')
assert.deepEqual(duplicates.map(item => item.id), [
  '2026年规划方案', '一客户基本画像', '一客户基本画像-2', '一客户基本画像-3',
])

const plainWrapped = `\`\`\`
# 普通围栏报告
## 一、概况
正文
\`\`\``
assert.equal(normalizeReportMarkdown(plainWrapped), '# 普通围栏报告\n## 一、概况\n正文')

console.log('report markdown normalization tests passed')
