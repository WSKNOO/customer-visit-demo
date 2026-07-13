<template>
  <div
    class="glass-panel"
    :class="[
      `glass-panel--${variant}`,
      { 'glass-panel--hover': hoverable, 'glass-panel--clickable': clickable }
    ]"
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
  variant?: 'default' | 'glow' | 'subtle' | 'dark'
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

const paddings = {
  sm: '12px',
  md: '20px',
  lg: '28px',
  xl: '36px',
}

const radiusMap = {
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
}
</script>

<style scoped>
.glass-panel {
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.glass-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: inherit;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.05), transparent 50%);
  pointer-events: none;
}

.glass-panel--glow {
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 40px rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.15);
}

.glass-panel--subtle {
  background: rgba(255, 255, 255, 0.02);
  backdrop-filter: blur(10px);
  border-color: rgba(255, 255, 255, 0.04);
}

.glass-panel--dark {
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(20px);
}

.glass-panel--hover:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.4), 0 0 60px rgba(99, 102, 241, 0.12);
  transform: translateY(-1px);
}

.glass-panel--clickable {
  cursor: pointer;
}

.glass-panel--clickable:active {
  transform: scale(0.98);
}
</style>