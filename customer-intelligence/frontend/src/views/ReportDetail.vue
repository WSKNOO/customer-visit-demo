<template>
  <div class="report-detail">
    <!-- Loading -->
    <div v-if="store.loading" class="report-detail__loading">
      <a-spin size="large" />
      <p class="report-detail__loading-text">正在加载报告...</p>
    </div>

    <!-- Error -->
    <div v-else-if="store.error" class="report-detail__error">
      <CloseCircleOutlined class="report-detail__error-icon" />
      <h3>加载失败</h3>
      <p>{{ store.error }}</p>
      <a-button @click="goBack">返回列表</a-button>
    </div>

    <!-- Report Content -->
    <template v-else-if="store.currentReport">
      <div class="report-detail__layout">
        <!-- Left Sidebar: TOC -->
        <aside class="report-detail__sidebar" :class="{ 'report-detail__sidebar--collapsed': !sidebarOpen }">
          <div v-if="sidebarOpen" class="report-detail__sidebar-panel">
            <div class="report-detail__sidebar-inner">
              <SectionTree
                :headings="headings"
                :activeIndex="activeHeading"
                @toggle="sidebarOpen = false"
                @scroll="scrollToHeading"
              />
            </div>
          </div>
          <button v-else class="report-detail__sidebar-trigger" @click="sidebarOpen = true">
            <MenuUnfoldOutlined />
          </button>
        </aside>

        <!-- Main: Content -->
        <main class="report-detail__main">
          <!-- Top Bar -->
          <div class="report-detail__topbar">
            <a-button @click="goBack" class="report-detail__topbar-btn">
              <ArrowLeftOutlined /> 返回
            </a-button>
            <span class="report-detail__topbar-title">{{ store.currentReport.company }}</span>
            <div class="report-detail__topbar-actions">
              <a-button
                type="primary"
                class="report-detail__training-btn"
                :loading="trainingLoading"
                :disabled="!store.currentReport"
                @click="startTraining"
              >
                <RocketOutlined /> 开始AI对练
              </a-button>
              <a-tooltip title="切换目录">
                <a-button class="report-detail__topbar-btn" @click="sidebarOpen = !sidebarOpen">
                  <MenuOutlined />
                </a-button>
              </a-tooltip>
              <a-tooltip title="回到顶部">
                <a-button class="report-detail__topbar-btn" @click="scrollToTop">
                  <VerticalAlignTopOutlined />
                </a-button>
              </a-tooltip>
            </div>
          </div>

          <!-- Header -->
          <ReportHeader
            :company="store.currentReport.company"
            :date="parsedDate"
            :lines="store.currentReport.lines"
            :chars="store.currentReport.chars"
            :sources="store.currentReport.sources"
          />

          <a-alert
            v-if="isMockOrCachedReport"
            class="report-detail__notice"
            type="warning"
            show-icon
            message="当前展示Mock或缓存演示结果"
            description="该结果用于演示兜底，不代表实时联网检索结果。"
          />
          <a-alert
            v-if="trainingMessage"
            class="report-detail__notice"
            :type="trainingMessageType"
            show-icon
            closable
            :message="trainingMessage"
            @close="trainingMessage = ''"
          />

          <!-- Content -->
          <ContentViewer
            ref="contentViewerRef"
            :markdown="normalizedReportMarkdown"
          />
        </main>
      </div>
    </template>

    <!-- No report -->
    <div v-else class="report-detail__empty">
      <FileUnknownOutlined />
      <p>未找到报告</p>
      <a-button @click="goBack">返回列表</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeftOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  VerticalAlignTopOutlined,
  CloseCircleOutlined,
  FileUnknownOutlined,
  RocketOutlined,
} from '@ant-design/icons-vue'
import ReportHeader from '@/components/ReportHeader.vue'
import SectionTree, { type HeadingItem } from '@/components/SectionTree.vue'
import ContentViewer from '@/components/ContentViewer.vue'
import { useReportStore } from '@/stores/reportStore'
import { startTrainingFromReport } from '@/api'
import { normalizeReportMarkdown, parseReportHeadings } from '@/utils/reportMarkdown'

const route = useRoute()
const router = useRouter()
const store = useReportStore()
const sidebarOpen = ref(true)
const activeHeading = ref(0)
const contentViewerRef = ref<InstanceType<typeof ContentViewer> | null>(null)
const trainingLoading = ref(false)
const trainingMessage = ref('')
const trainingMessageType = ref<'success' | 'error' | 'info' | 'warning'>('info')

const filename = computed(() => route.params.filename as string)

const parsedDate = computed(() => {
  if (!store.currentReport) return ''
  const m = store.currentReport.filename.match(/(\d{8})_(\d{6})/)
  return m ? `${m[1].slice(0,4)}-${m[1].slice(4,6)}-${m[1].slice(6,8)}` : ''
})

const isMockOrCachedReport = computed(() => /Mock|缓存演示结果/.test(store.currentReport?.content || ''))

const normalizedReportMarkdown = computed(() =>
  normalizeReportMarkdown(store.currentReport?.content || ''),
)

// ContentViewer uses the same normalized Markdown and parser, keeping tree indexes aligned.
const headings = computed<HeadingItem[]>(() => parseReportHeadings(normalizedReportMarkdown.value))

onMounted(() => {
  if (filename.value) store.loadReport(filename.value)
})

watch(filename, (v) => {
  if (v) { store.loadReport(v); sidebarOpen.value = true; activeHeading.value = 0 }
})

function goBack() { router.push({ name: 'ReportList' }) }

function scrollToHeading(index: number) {
  activeHeading.value = index
  nextTick(() => {
    contentViewerRef.value?.scrollToHeading(index)
  })
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function startTraining() {
  if (!store.currentReport || trainingLoading.value) return
  trainingLoading.value = true
  trainingMessage.value = '正在创建陪练会话...'
  trainingMessageType.value = 'info'
  try {
    const result = await startTrainingFromReport(store.currentReport.filename)
    trainingMessage.value = '陪练会话创建成功，正在跳转...'
    trainingMessageType.value = 'success'
    window.location.assign(result.training_url)
  } catch (error: any) {
    const code = error?.response?.data?.error_code
    trainingMessageType.value = 'error'
    if (code === 'TRAINING_CONNECT_TIMEOUT' || code === 'TRAINING_READ_TIMEOUT') {
      trainingMessage.value = '创建陪练会话超时，可以稍后重试；当前情报结果不会丢失。'
    } else if (code === 'VISIT_BRIEF_INVALID' || code === 'VISIT_BRIEF_REJECTED') {
      trainingMessage.value = '客户情报数据校验失败，请检查报告内容后重试。'
    } else {
      trainingMessage.value = '陪练服务暂不可用，可以稍后重试；当前情报结果不会丢失。'
    }
  } finally {
    trainingLoading.value = false
  }
}
</script>

<style scoped>
.report-detail {
  min-height: 100vh;
  background: var(--bg-page);
}

/* ── Loading ── */
.report-detail__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  gap: 16px;
}
.report-detail__loading-text { color: var(--text-secondary); font-size: 15px; }

/* ── Error ── */
.report-detail__error {
  text-align: center; padding: 60px 40px; margin: 80px auto; max-width: 440px;
}
.report-detail__error-icon { font-size: 48px; color: var(--error); margin-bottom: 16px; }
.report-detail__error h3 { font-size: 18px; margin-bottom: 8px; color: var(--text-primary); }
.report-detail__error p { color: var(--text-tertiary); margin-bottom: 20px; }

/* ── Layout ── */
.report-detail__layout {
  display: flex;
  min-height: 100vh;
}

/* ── Sidebar ── */
.report-detail__sidebar {
  width: 260px;
  flex-shrink: 0;
  transition: width var(--transition-normal);
}
.report-detail__sidebar--collapsed { width: 48px; }
.report-detail__sidebar-panel {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 8px 0 8px 8px;
}
.report-detail__sidebar-inner {
  height: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}
.report-detail__sidebar-trigger {
  position: sticky;
  top: 16px;
  width: 36px; height: 36px;
  margin: 12px auto;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.report-detail__sidebar-trigger:hover { border-color: var(--primary); color: var(--primary); }

/* ── Main ── */
.report-detail__main {
  flex: 1;
  min-width: 0;
  padding: 0 40px 80px;
}

/* ── Top Bar ── */
.report-detail__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(245, 247, 250, 0.9);
  backdrop-filter: blur(8px);
  margin-bottom: 8px;
  gap: 12px;
}
.report-detail__topbar-btn {
  display: inline-flex !important;
  align-items: center !important;
  gap: 5px !important;
  border-radius: var(--radius-md) !important;
  font-size: 13px !important;
}
.report-detail__topbar-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.report-detail__topbar-actions { display: flex; gap: 6px; }
.report-detail__training-btn { display: inline-flex !important; align-items: center !important; gap: 5px !important; }
.report-detail__notice { margin: 12px 0 18px; }

/* ── Empty ── */
.report-detail__empty {
  text-align: center; padding: 60px 40px; margin: 80px auto; max-width: 400px;
  display: flex; flex-direction: column; align-items: center; gap: 16px;
  color: var(--text-tertiary); font-size: 16px;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .report-detail__sidebar { display: none; }
  .report-detail__main { padding: 0 16px 40px; }
}
</style>
