<template>
  <div class="section-tree">
    <div class="section-tree__header">
      <span class="section-tree__title">目录</span>
      <button class="section-tree__toggle" @click="$emit('toggle')">
        <MenuFoldOutlined />
      </button>
    </div>
    <div class="section-tree__list">
      <template v-for="(h, i) in headings" :key="i">
        <div
          v-if="h.level <= 3"
          class="section-tree__item"
          :class="[
            `section-tree__item--level-${h.level}`,
            { 'section-tree__item--active': activeIndex === i }
          ]"
          @click="scrollTo(i)"
        >
          <span class="section-tree__item-title" :title="h.text">{{ h.text }}</span>
        </div>
      </template>
    </div>
    <div v-if="!headings.length" class="section-tree__empty">无目录</div>
  </div>
</template>

<script setup lang="ts">
import { MenuFoldOutlined } from '@ant-design/icons-vue'

export interface HeadingItem {
  level: number
  text: string
}

defineProps<{ headings: HeadingItem[]; activeIndex: number }>()
const emit = defineEmits<{ toggle: []; scroll: [index: number] }>()

function scrollTo(index: number) {
  emit('scroll', index)
}
</script>

<style scoped>
.section-tree {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.section-tree__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 14px;
  border-bottom: 1px solid var(--border-light);
}
.section-tree__title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.section-tree__toggle {
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  font-size: 14px;
}
.section-tree__toggle:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.section-tree__list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 4px;
}

.section-tree__item {
  padding: 6px 10px;
  margin: 1px 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.section-tree__item:hover {
  background: var(--bg-hover);
}
.section-tree__item--active {
  background: var(--primary-bg) !important;
  border-left: 2px solid var(--primary);
}

.section-tree__item-title {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.4;
}
.section-tree__item--active .section-tree__item-title {
  color: var(--primary);
  font-weight: 600;
}

.section-tree__item--level-1 { padding-left: 12px; }
.section-tree__item--level-1 .section-tree__item-title {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 13px;
}
.section-tree__item--level-2 { padding-left: 26px; }
.section-tree__item--level-2 .section-tree__item-title { font-size: 12.5px; }
.section-tree__item--level-3 { padding-left: 40px; }
.section-tree__item--level-3 .section-tree__item-title { font-size: 12px; color: var(--text-tertiary); }

.section-tree__empty {
  padding: 24px 14px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
}
</style>