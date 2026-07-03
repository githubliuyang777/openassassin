<template>
  <div
    v-if="alerts.length > 0"
    class="alert-banner-wrapper"
    :class="`severity-${maxSeverity}`"
  >
    <div class="alert-banner-inner">
      <div class="marquee-track">
        <span class="marquee-content">{{ joinedMessages }}</span>
        <span class="marquee-content" aria-hidden="true">{{ joinedMessages }}</span>
      </div>
    </div>
    <n-button text class="dismiss-btn" @click="$emit('dismiss')">
      <template #icon><n-icon><CloseOutline /></n-icon></template>
    </n-button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { CloseOutline } from '@vicons/ionicons5'
import type { AlertItem } from '@/api/alerts'

const props = defineProps<{ alerts: AlertItem[] }>()
defineEmits<{ dismiss: [] }>()

const joinedMessages = computed(() =>
  props.alerts.map((a) => a.message).join('  |  ')
)

const severityRank: Record<string, number> = { danger: 0, warning: 1, info: 2 }

const maxSeverity = computed(() => {
  if (props.alerts.length === 0) return 'info'
  let worst = 'info'
  for (const a of props.alerts) {
    if (severityRank[a.severity] < severityRank[worst]) {
      worst = a.severity
    }
  }
  return worst
})
</script>

<style scoped>
.alert-banner-wrapper {
  height: 36px;
  display: flex;
  align-items: center;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
  overflow: hidden;
  position: relative;
}

.alert-banner-wrapper.severity-danger {
  background: #d03050;
  color: #fff;
}
.alert-banner-wrapper.severity-warning {
  background: #f0a020;
  color: #fff;
}
.alert-banner-wrapper.severity-info {
  background: #2080f0;
  color: #fff;
}

.alert-banner-inner {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  min-width: 0;
}

.marquee-track {
  display: inline-flex;
  animation: marquee 30s linear infinite;
}

.marquee-content {
  padding-right: 80px;
  font-size: 13px;
  line-height: 36px;
}

.dismiss-btn {
  flex-shrink: 0;
  color: inherit !important;
  margin: 0 4px;
}

@keyframes marquee {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-50%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .marquee-track {
    animation: none;
  }
}
</style>
