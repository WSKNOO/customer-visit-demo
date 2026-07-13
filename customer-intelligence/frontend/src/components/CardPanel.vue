<template>
  <div
    class="card-panel"
    :class="[`card-panel--${variant}`, { 'card-panel--hover': hoverable, 'card-panel--clickable': clickable }]"
    :style="{
      padding: paddings[paddingSize],
      borderRadius: radiusMap[radius],
    }"
  >
    <slot />
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  variant?: 'default' | 'elevated' | 'bordered' | 'ghost'
  paddingSize?: 'sm' | 'md' | 'lg' | 'xl'
  radius?: 'sm' | 'md' | 'lg' | 'xl'
  hoverable?: boolean
  clickable?: boolean
}>(), {
  variant: 'default',
  paddingSize: 'md',
  radius: 'lg',
  hoverable: false,
  clickable: false,
})

const paddings: Record<string, string> = {
  sm: '12px',
  md: '20px',
  lg: '28px',
  xl: '36px',
}

const radiusMap: Record<string, string> = {
  sm: '6px',
  md: '8px',
  lg: '12px',
  xl: '16px',
}
</script>

<style scoped>
.card-panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  transition: all var(--transition-normal);
}

.card-panel--default {
  box-shadow: var(--shadow-sm);
}

.card-panel--elevated {
  box-shadow: var(--shadow-md);
  border-color: transparent;
}

.card-panel--bordered {
  box-shadow: none;
  background: transparent;
}

.card-panel--ghost {
  box-shadow: none;
  border: none;
  background: transparent;
}

.card-panel--hover:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-md);
}

.card-panel--clickable {
  cursor: pointer;
}

.card-panel--clickable:active {
  transform: scale(0.98);
}
</style>