<template>
  <div class="content-viewer">
    <div class="content-viewer__body" ref="bodyRef" v-html="renderedHtml"></div>

    <div v-if="!markdown" class="content-viewer__empty">
      <FileSearchOutlined />
      <p>暂无报告内容</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { FileSearchOutlined } from '@ant-design/icons-vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

marked.use({ gfm: true, breaks: true })

const props = defineProps<{ markdown: string }>()

const bodyRef = ref<HTMLElement | null>(null)
const headingIds = ref<string[]>([])

const renderedHtml = computed(() => {
  if (!props.markdown) return ''

  // Process code blocks with highlight.js
  const processed = props.markdown.replace(/```(\w*)\n([\s\S]*?)```/g, (_m: string, lang: string, code: string) => {
    let highlighted: string
    if (lang && hljs.getLanguage(lang)) {
      highlighted = hljs.highlight(code, { language: lang }).value
    } else {
      highlighted = hljs.highlightAuto(code).value
    }
    return `<pre><code class="hljs language-${lang || 'plaintext'}">${highlighted}</code></pre>`
  })

  // Add id attributes to headings so we can anchor-scroll
  const withIds = processed.replace(/^(#{1,4})\s+(.+)$/gm, (_m: string, hashes: string, title: string) => {
    const id = title
      .replace(/\*\*/g, '')
      .replace(/[。，、；：？！\s]+/g, '-')
      .replace(/[^\w一-鿿-]/g, '')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .toLowerCase()
      || `h-${Math.random().toString(36).slice(2, 6)}`
    return `${hashes} <span id="${id}"></span>${title}`
  })

  // Extract heading IDs for external navigation
  const ids: string[] = []
  props.markdown.replace(/^(#{1,4})\s+(.+)$/gm, (_m: string, _hashes: string, title: string) => {
    const id = title
      .replace(/\*\*/g, '')
      .replace(/[。，、；：？！\s]+/g, '-')
      .replace(/[^\w一-鿿-]/g, '')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .toLowerCase()
    ids.push(id || `h-${ids.length}`)
    return ''
  })
  headingIds.value = ids

  return marked.parse(withIds, { async: false }) as string
})

// Expose scrollToHeading for parent to call
function scrollToHeading(index: number) {
  const id = headingIds.value[index]
  if (!id || !bodyRef.value) return
  const el = bodyRef.value.querySelector(`#${CSS.escape(id)}`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

defineExpose({ scrollToHeading })
</script>

<style scoped>
.content-viewer {
  max-width: 860px;
  margin: 0 auto;
}

.content-viewer__body {
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-secondary);
}

/* ── Headings ── */
.content-viewer__body :deep(h1) {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 40px 0 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
  letter-spacing: -0.01em;
}

.content-viewer__body :deep(h2) {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 32px 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-light);
}

.content-viewer__body :deep(h3) {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 24px 0 8px;
}

.content-viewer__body :deep(h4) {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 18px 0 6px;
}

/* ── Paragraph ── */
.content-viewer__body :deep(p) {
  margin: 0 0 10px;
  color: var(--text-secondary);
}

/* ── Tables ── */
.content-viewer__body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 14px;
}
.content-viewer__body :deep(th) {
  background: var(--bg-hover);
  padding: 10px 12px;
  font-weight: 600;
  color: var(--text-primary);
  border: 1px solid var(--border);
  text-align: left;
}
.content-viewer__body :deep(td) {
  padding: 9px 12px;
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
}
.content-viewer__body :deep(tr:nth-child(even)) {
  background: #fafbfc;
}

/* ── Blockquote ── */
.content-viewer__body :deep(blockquote) {
  border-left: 3px solid var(--primary);
  padding: 12px 18px;
  margin: 14px 0;
  background: var(--primary-bg);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--text-secondary);
}
.content-viewer__body :deep(blockquote p) {
  margin: 0;
}

/* ── Code ── */
.content-viewer__body :deep(pre) {
  background: #f6f8fa;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  overflow-x: auto;
  margin: 14px 0;
}
.content-viewer__body :deep(code) {
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
}
.content-viewer__body :deep(:not(pre) > code) {
  background: var(--primary-bg);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--primary);
  font-size: 13px;
}

/* ── Inline ── */
.content-viewer__body :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}
.content-viewer__body :deep(ul),
.content-viewer__body :deep(ol) {
  padding-left: 22px;
  margin: 8px 0;
}
.content-viewer__body :deep(li) {
  margin-bottom: 4px;
}
.content-viewer__body :deep(hr) {
  border: none;
  height: 1px;
  background: var(--border-light);
  margin: 24px 0;
}

/* ── Images ── */
.content-viewer__body :deep(img) {
  max-width: 100%;
  border-radius: var(--radius-md);
  margin: 16px 0;
}

/* ── Anchor spans ── */
.content-viewer__body :deep(span[id]) {
  display: inline;
  scroll-margin-top: 80px;
}

/* ── Empty ── */
.content-viewer__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px;
  color: var(--text-tertiary);
  gap: 10px;
  font-size: 15px;
}
</style>