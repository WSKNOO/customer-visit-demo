<template>
  <div class="report-header">
    <div class="report-header__top">
      <div class="report-header__company-section">
        <h1 class="report-header__company">{{ company }}</h1>
        <div class="report-header__tags">
          <span class="report-header__tag">
            <CalendarOutlined /> {{ date }}
          </span>
          <span class="report-header__tag">
            <FileTextOutlined /> {{ lines.toLocaleString() }} 行
          </span>
          <span class="report-header__tag">
            <BookOutlined /> {{ (chars / 10000).toFixed(1) }} 万字
          </span>
          <span v-if="sources > 0" class="report-header__tag">
            <LinkOutlined /> {{ sources }} 个来源
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CalendarOutlined, FileTextOutlined, BookOutlined, LinkOutlined } from '@ant-design/icons-vue'

defineProps<{
  company: string
  date: string
  lines: number
  chars: number
  sources: number
}>()
</script>

<style scoped>
.report-header {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 28px 32px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-sm);
}

.report-header__company {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
  letter-spacing: -0.01em;
}

.report-header__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.report-header__tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--text-tertiary);
  background: var(--bg-tag);
  padding: 3px 10px;
  border-radius: 6px;
}
</style>