<template>
  <n-button
    type="error"
    secondary
    :size="size"
    :disabled="count === 0"
    :loading="loading"
    @click="handleClick"
  >
    批量删除{{ count ? ` (${count})` : '' }}
  </n-button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NButton, useDialog, useMessage } from 'naive-ui'

const MAX_BATCH_DELETE = 500

const props = withDefaults(defineProps<{
  count: number
  noun: string
  action: () => Promise<void>
  size?: 'tiny' | 'small'
}>(), {
  size: 'small',
})

const dialog = useDialog()
const message = useMessage()
const loading = ref(false)

function handleClick() {
  if (props.count === 0 || loading.value) return
  if (props.count > MAX_BATCH_DELETE) {
    message.warning(`单次最多删除 ${MAX_BATCH_DELETE} 项`)
    return
  }
  dialog.warning({
    title: `批量删除${props.noun}`,
    content: `确定删除选中的 ${props.count} 个${props.noun}吗？此操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    positiveButtonProps: { type: 'error' },
    onPositiveClick: async () => {
      loading.value = true
      try {
        await props.action()
      } catch {
        // The page shows the backend error and keeps the selection for retry.
      } finally {
        loading.value = false
      }
    },
  })
}
</script>
