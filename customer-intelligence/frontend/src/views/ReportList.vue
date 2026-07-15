<template>
  <div class="report-list">
    <!-- Hero Section -->
    <div class="report-list__hero">
      <p class="report-list__badge">产数售前助手 · 拜访准备</p>
      <h1 class="report-list__title">客户拜访情报助手</h1>
      <p class="report-list__subtitle">联网洞察客户背景、行业动态与数字化线索，智能生成拜访情报简报</p>
      <div class="report-list__actions">
        <a-button type="primary" size="large" @click="showNewResearch = true">
          <template #icon><PlusOutlined /></template>
          生成拜访情报
        </a-button>
        <a-button size="large" @click="refresh" :loading="store.loading">
          <template #icon><ReloadOutlined /></template>
          刷新列表
        </a-button>
      </div>
    </div>

    <a-alert
      v-if="researchStatusMessage"
      class="report-list__status"
      :type="researchStatusType"
      show-icon
      closable
      :message="researchStatusMessage"
      :description="researchRequestId ? `请求编号：${researchRequestId}` : undefined"
      @close="researchStatusMessage = ''"
    />

    <!-- Search & Filter Bar -->
    <div class="report-list__toolbar">
      <a-input
        v-model:value="searchQuery"
        placeholder="搜索公司名称..."
        class="report-list__search"
        allow-clear
        prefixCls="search-input"
      >
        <template #prefix><SearchOutlined /></template>
      </a-input>
      <div class="report-list__stats">
        共 <strong>{{ filteredReports.length }}</strong> 份报告
      </div>
    </div>

    <!-- Loading Skeleton -->
    <div v-if="store.loading && !store.reports.length" class="report-list__loading">
      <a-skeleton v-for="i in 4" :key="i" class="report-list__skeleton" active :paragraph="{ rows: 3 }" />
    </div>

    <!-- Empty State -->
    <div v-else-if="!filteredReports.length" class="report-list__empty">
      <FileSearchOutlined class="report-list__empty-icon" />
      <h3>{{ searchQuery ? '未找到匹配的报告' : '暂无研究报告' }}</h3>
      <p>{{ searchQuery ? '尝试其他搜索关键词' : '点击「发起新研究」开始生成第一份报告' }}</p>
    </div>

    <!-- Report Grid -->
    <div v-else class="report-list__grid">
      <div
        v-for="(report, i) in filteredReports"
        :key="report.filename"
        class="report-list__card"
        :style="{ '--delay': `${i * 0.04}s` }"
        @click="goToReport(report.filename)"
      >
        <div class="report-list__card-top">
          <div class="report-list__card-avatar" :style="{ background: avatarColors[i % avatarColors.length] }">
            {{ report.company.charAt(0) }}
          </div>
          <div class="report-list__card-info">
            <h3 class="report-list__card-company">{{ report.company }}</h3>
            <span class="report-list__card-date">{{ report.date || '未知日期' }}</span>
          </div>
        </div>
        <div class="report-list__card-meta">
          <span><FileTextOutlined /> {{ report.size_kb }} KB</span>
          <span><BarsOutlined /> {{ report.lines.toLocaleString() }} 行</span>
        </div>
        <div class="report-list__card-footer">
          <span>查看详情</span>
          <RightOutlined />
        </div>
      </div>
    </div>

    <!-- New Research Modal -->
    <a-modal
      v-model:open="showNewResearch"
      title="生成客户拜访情报"
      :footer="null"
      destroyOnClose
      :width="520"
      class="research-modal"
    >
      <a-form layout="vertical" :model="researchForm" @finish="handleResearch">
        <a-form-item label="公司名称" name="company_name" :rules="[{ required: true, message: '请输入公司名称' }]">
          <a-input
            v-model:value="researchForm.company_name"
            placeholder="例：中国石油天然气集团有限公司"
            size="large"
          />
        </a-form-item>
        <a-form-item label="拜访目的（可选）" name="visit_purpose">
          <a-textarea
            v-model:value="researchForm.visit_purpose"
            placeholder="例：了解数字化转型需求，推荐AI解决方案"
            :rows="2"
          />
        </a-form-item>
        <a-form-item label="重点关注领域（可选）" name="focus_areas">
          <a-input
            v-model:value="researchForm.focus_areas"
            placeholder="例：AI, 云, 大数据, 安全（用逗号分隔）"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="researching" block size="large">
            <template #icon><SearchOutlined /></template>
            开始生成
          </a-button>
        </a-form-item>
      </a-form>
      <div v-if="researchResult" class="research-modal__result">
        {{ researchResult }}
      </div>
      <a-divider>演示兜底</a-divider>
      <p class="research-modal__demo-hint">搜索或模型不可用时，可加载预生成的缓存演示结果。</p>
      <div class="research-modal__demo-list">
        <a-button
          v-for="demo in demoReports"
          :key="demo.id"
          :loading="loadingDemoId === demo.id"
          @click="loadDemo(demo.id)"
        >
          加载 {{ demo.customer_name }}
        </a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  SearchOutlined,
  PlusOutlined,
  ReloadOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  BarsOutlined,
  RightOutlined,
} from '@ant-design/icons-vue'
import { useReportStore } from '@/stores/reportStore'
import { startResearch, fetchResearchStatus, fetchDemoReports, loadDemoReport, type DemoReportOption } from '@/api'

const router = useRouter()
const store = useReportStore()
const searchQuery = ref('')
const showNewResearch = ref(false)
const researching = ref(false)
const researchResult = ref('')
const researchStatusMessage = ref('')
const researchStatusType = ref<'success' | 'error' | 'info' | 'warning'>('info')
const researchRequestId = ref('')
let pollTimer: ReturnType<typeof setTimeout> | null = null
const demoReports = ref<DemoReportOption[]>([])
const loadingDemoId = ref('')

const researchForm = ref({
  company_name: '',
  visit_purpose: '',
  focus_areas: '',
})

const avatarColors = [
  '#1677ff', '#722ed1', '#13c2c2', '#52c41a',
  '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911',
]

const filteredReports = computed(() => {
  if (!searchQuery.value) return store.reports
  const q = searchQuery.value.toLowerCase()
  return store.reports.filter(r => r.company.toLowerCase().includes(q))
})

onMounted(async () => {
  store.loadReports()
  try { demoReports.value = await fetchDemoReports() } catch { demoReports.value = [] }
})
onUnmounted(() => { if (pollTimer) clearTimeout(pollTimer) })

function refresh() { store.loadReports() }

function goToReport(filename: string) {
  router.push({ name: 'ReportDetail', params: { filename } })
}

async function handleResearch() {
  researching.value = true
  researchResult.value = ''
  try {
    const res = await startResearch(researchForm.value)
    researchResult.value = res.message
    researchStatusMessage.value = '正在生成客户情报，请稍候...'
    researchStatusType.value = 'info'
    researchRequestId.value = res.request_id || ''
    showNewResearch.value = false
    researchForm.value = { company_name: '', visit_purpose: '', focus_areas: '' }
    pollResearchStatus(res.task_id)
  } catch {
    researchResult.value = '暂时无法启动情报生成，请稍后重试；已有报告不会丢失。'
  } finally {
    researching.value = false
  }
}

async function pollResearchStatus(taskId: string) {
  try {
    const status = await fetchResearchStatus(taskId)
    researchRequestId.value = status.request_id || researchRequestId.value
    if (status.status === 'generating') {
      researchStatusType.value = 'info'
      researchStatusMessage.value = '正在生成客户情报，请稍候...'
      pollTimer = setTimeout(() => pollResearchStatus(taskId), 1200)
      return
    }
    if (status.status === 'success') {
      researchStatusType.value = status.result_mode === 'mock' ? 'warning' : 'success'
      researchStatusMessage.value = status.result_mode === 'mock'
        ? 'Mock客户情报生成成功，当前结果不是实时联网数据。' : '客户情报生成成功。'
      await store.loadReports()
      if (status.report_filename) router.push({ name: 'ReportDetail', params: { filename: status.report_filename } })
      return
    }
    researchStatusType.value = 'error'
    researchStatusMessage.value = status.message || '情报生成失败，可稍后重试或加载缓存演示结果。'
  } catch {
    researchStatusType.value = 'error'
    researchStatusMessage.value = '无法获取情报生成状态，请稍后刷新；已有报告不会丢失。'
  }
}

async function loadDemo(id: string) {
  if (loadingDemoId.value) return
  loadingDemoId.value = id
  try {
    const result = await loadDemoReport(id)
    showNewResearch.value = false
    researchStatusType.value = 'warning'
    researchStatusMessage.value = '已加载缓存演示结果，该内容不是实时联网数据。'
    researchRequestId.value = result.request_id
    await store.loadReports()
    router.push({ name: 'ReportDetail', params: { filename: result.report_filename } })
  } catch {
    researchResult.value = '加载缓存演示结果失败，请稍后重试。'
  } finally {
    loadingDemoId.value = ''
  }
}
</script>

<style scoped>
.report-list {
  max-width: 1080px;
  margin: 0 auto;
  padding: 48px 32px;
}

/* ── Hero ── */
.report-list__hero {
  text-align: center;
  padding: 40px 0 36px;
}
.report-list__badge {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-bg);
  padding: 4px 12px;
  border-radius: 20px;
  letter-spacing: 0.04em;
  margin-bottom: 16px;
  text-transform: uppercase;
}
.report-list__title {
  font-size: 36px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
  letter-spacing: -0.01em;
}
.report-list__subtitle {
  color: var(--text-tertiary);
  font-size: 15px;
  margin-bottom: 28px;
}
.report-list__actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}
.report-list__status { margin: 0 0 24px; }
.research-modal__demo-hint { color: var(--text-tertiary); font-size: 13px; }
.research-modal__demo-list { display: flex; flex-wrap: wrap; gap: 8px; }

/* ── Toolbar ── */
.report-list__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  padding: 12px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.report-list__search {
  max-width: 300px;
  border-radius: var(--radius-md);
}
.report-list__stats {
  font-size: 13px;
  color: var(--text-tertiary);
}
.report-list__stats strong {
  color: var(--text-primary);
}

/* ── Loading ── */
.report-list__loading {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}
.report-list__skeleton {
  background: var(--bg-card);
  padding: 24px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
}

/* ── Empty ── */
.report-list__empty {
  text-align: center;
  padding: 80px 24px;
  color: var(--text-tertiary);
}
.report-list__empty-icon {
  font-size: 48px;
  color: var(--text-tertiary);
  margin-bottom: 16px;
}
.report-list__empty h3 {
  font-size: 18px;
  color: var(--text-primary);
  margin-bottom: 6px;
}
.report-list__empty p {
  font-size: 14px;
}

/* ── Grid ── */
.report-list__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}
.report-list__card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  cursor: pointer;
  transition: all var(--transition-normal);
  box-shadow: var(--shadow-sm);
  animation: cardIn 0.4s ease forwards;
  animation-delay: var(--delay);
  opacity: 0;
  transform: translateY(12px);
  display: flex;
  flex-direction: column;
}
.report-list__card:hover {
  border-color: var(--primary-border);
  box-shadow: 0 4px 20px rgba(22, 119, 255, 0.10);
  transform: translateY(-2px);
}

@keyframes cardIn {
  to { opacity: 1; transform: translateY(0); }
}

.report-list__card-top {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}
.report-list__card-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}
.report-list__card-info {
  min-width: 0;
}
.report-list__card-company {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.report-list__card-date {
  font-size: 13px;
  color: var(--text-tertiary);
}
.report-list__card-meta {
  display: flex;
  gap: 20px;
  font-size: 13px;
  color: var(--text-tertiary);
  margin-bottom: 16px;
}
.report-list__card-meta span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.report-list__card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 14px;
  border-top: 1px solid var(--border-light);
  font-size: 13px;
  font-weight: 500;
  color: var(--primary);
  margin-top: auto;
}
.report-list__card-footer span {
  transition: margin-right var(--transition-fast);
}
.report-list__card:hover .report-list__card-footer span {
  margin-right: 4px;
}

/* ── Result Toast ── */
.research-modal__result {
  background: var(--bg-page);
  border-radius: var(--radius-md);
  padding: 16px;
  font-size: 14px;
  color: var(--text-secondary);
  text-align: center;
  margin-top: 16px;
}
</style>
