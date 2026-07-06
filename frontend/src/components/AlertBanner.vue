<template>
  <div
    v-if="alerts.length > 0"
    class="alert-banner-wrapper"
    :class="`severity-${maxSeverity}`"
  >
    <div class="alert-banner-inner">
      <span class="banner-text">{{ joinedMessages }}</span>
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
  text-align: center;
  min-width: 0;
}

.banner-text {
  font-size: 13px;
  line-height: 36px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

.dismiss-btn {
  flex-shrink: 0;
  color: inherit !important;
  margin: 0 4px;
}
</style>
