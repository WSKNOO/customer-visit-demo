export interface ReportHeading {
  level: number
  text: string
  id: string
}

interface FenceBlock {
  start: number
  end: number
  info: string
  body: string
  raw: string
}

const HEADING_RE = /^#{1,4}\s+\S/m
const EXPLANATORY_PREFACE_RE = /(?:好的|下面|以下|我来|我需要|根据.{0,20}材料|为您整理|开始.{0,10}(?:生成|整理))/

function collectFenceBlocks(markdown: string): FenceBlock[] {
  const lines = markdown.split('\n')
  const blocks: FenceBlock[] = []
  let opening: { start: number; marker: string; info: string } | null = null

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    if (!opening) {
      const match = line.match(/^ {0,3}(`{3,}|~{3,})\s*([^\s`]*)?\s*$/)
      if (match) opening = { start: index, marker: match[1], info: (match[2] || '').toLowerCase() }
      continue
    }

    const markerChar = opening.marker[0]
    const closing = line.match(/^ {0,3}(`{3,}|~{3,})\s*$/)
    if (!closing || closing[1][0] !== markerChar || closing[1].length < opening.marker.length) continue

    const body = lines.slice(opening.start + 1, index).join('\n')
    blocks.push({
      start: opening.start,
      end: index,
      info: opening.info,
      body,
      raw: lines.slice(opening.start, index + 1).join('\n'),
    })
    opening = null
  }

  return blocks
}

function cleanHeadingText(title: string): string {
  return title
    .replace(/\s+#+\s*$/, '')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[\*_`~]/g, '')
    .trim()
}

export function normalizeReportMarkdown(markdown: string): string {
  const source = String(markdown || '').replace(/\r\n?/g, '\n').trim()
  if (!source) return ''

  const blocks = collectFenceBlocks(source)
  const explicitReportBlocks = blocks.filter(
    block => (block.info === 'markdown' || block.info === 'md') && HEADING_RE.test(block.body),
  )

  if (explicitReportBlocks.length) {
    const first = explicitReportBlocks[0].start
    const last = explicitReportBlocks[explicitReportBlocks.length - 1].end
    const reportParts: string[] = []
    for (const block of blocks) {
      if (block.start < first || block.end > last) continue
      if ((block.info === 'markdown' || block.info === 'md') && HEADING_RE.test(block.body)) {
        reportParts.push(block.body.trim())
      } else if (block.info && block.info !== 'markdown' && block.info !== 'md') {
        reportParts.push(block.raw.trim())
      }
    }
    return reportParts.filter(Boolean).join('\n\n').trim()
  }

  const sourceLines = source.split('\n')
  const plainReportBlock = blocks.find(block => {
    if (block.info) return false
    const headingCount = (block.body.match(/^#{1,4}\s+\S/gm) || []).length
    const looksLikeReport = /^#\s+.*(?:情报|简报|报告)/m.test(block.body) || headingCount >= 2
    const before = sourceLines.slice(0, block.start).join('\n').trim()
    const after = sourceLines.slice(block.end + 1).join('\n').trim()
    return looksLikeReport && (!before || EXPLANATORY_PREFACE_RE.test(before)) && !after
  })
  if (plainReportBlock) return plainReportBlock.body.trim()

  const firstHeading = source.search(/^#{1,4}\s+\S/m)
  if (firstHeading > 0) {
    const prefix = source.slice(0, firstHeading).trim()
    if (EXPLANATORY_PREFACE_RE.test(prefix)) return source.slice(firstHeading).trim()
  }

  return source
}

export function compactHeadingId(title: string): string {
  return cleanHeadingText(title)
    .normalize('NFKC')
    .replace(/[^\p{L}\p{N}]/gu, '')
    .toLowerCase() || 'section'
}

export function parseReportHeadings(markdown: string): ReportHeading[] {
  const normalized = normalizeReportMarkdown(markdown)
  const lines = normalized.split('\n')
  const counts = new Map<string, number>()
  const headings: ReportHeading[] = []
  let fence: { marker: string } | null = null

  for (const line of lines) {
    if (!fence) {
      const opening = line.match(/^ {0,3}(`{3,}|~{3,})(?:\s*[^\s`]*)?\s*$/)
      if (opening) fence = { marker: opening[1] }
      if (opening) continue
    } else {
      const closing = line.match(/^ {0,3}(`{3,}|~{3,})\s*$/)
      if (closing && fence.marker[0] === closing[1][0] && closing[1].length >= fence.marker.length) {
        fence = null
      }
      continue
    }

    const match = line.match(/^(#{1,4})\s+(.+?)\s*$/)
    if (!match) continue
    const text = cleanHeadingText(match[2])
    const base = compactHeadingId(text)
    const count = (counts.get(base) || 0) + 1
    counts.set(base, count)
    headings.push({ level: match[1].length, text, id: count === 1 ? base : `${base}-${count}` })
  }

  return headings
}
