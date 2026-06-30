<template>
  <div style="max-width: 1000px">
    <n-h3>执行脚本: {{ script?.name }}</n-h3>

    <n-card title="脚本信息" style="margin-bottom: 16px">
      <n-descriptions :columns="2" label-placement="left">
        <n-descriptions-item label="类型">
          <n-tag :type="script?.type === 'python' ? 'info' : 'success'" size="small">{{ script?.type }}</n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="超时">{{ script?.timeout }}s</n-descriptions-item>
        <n-descriptions-item label="描述" :span="2">{{ script?.description || '-' }}</n-descriptions-item>
      </n-descriptions>
    </n-card>

    <n-card title="注入密钥" style="margin-bottom: 16px">
      <n-checkbox-group v-model:value="selectedCredentials">
        <n-space v-if="credentials.length">
          <n-checkbox v-for="c in credentials" :key="c.id" :value="c.id">
            {{ c.name }} <n-text depth="3">(${{ c.key }})</n-text>
          </n-checkbox>
        </n-space>
        <n-text v-else depth="3">暂无可用密钥</n-text>
      </n-checkbox-group>
    </n-card>

    <n-button type="primary" :loading="running" @click="handleExecute" style="margin-bottom: 16px">
      <template #icon><n-icon><PlayOutline /></n-icon></template>
      执行
    </n-button>

    <n-card v-if="result" title="执行结果" :bordered="true">
      <n-space style="margin-bottom: 8px">
        <n-tag :type="statusTagType">{{ result.status }}</n-tag>
        <n-text v-if="result.exit_code !== undefined">退出码: {{ result.exit_code }}</n-text>
      </n-space>
      <n-log :log="resultLog" :rows="20" language="log" style="font-family: monospace; font-size: 13px" />
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  NH3, NCard, NDescriptions, NDescriptionsItem, NTag, NText,
  NCheckboxGroup, NCheckbox, NSpace, NButton, NIcon, NLog, useMessage,
} from 'naive-ui'
import { PlayOutline } from '@vicons/ionicons5'
import { fetchScript, executeScript } from '@/api/scripts'
import { fetchCredentials } from '@/api/credentials'
import type { Script } from '@/api/scripts'
import type { Credential } from '@/api/credentials'

const route = useRoute()
const message = useMessage()

const script = ref<Script | null>(null)
const credentials = ref<Credential[]>([])
const selectedCredentials = ref<number[]>([])
const running = ref(false)
const result = ref<any>(null)

const resultLog = computed(() => result.value?.log || '')
const statusTagType = computed(() => {
  const m: Record<string, any> = { success: 'success', failed: 'error', timeout: 'warning', running: 'info' }
  return m[result.value?.status] || 'default'
})

onMounted(async () => {
  const [sRes, cRes] = await Promise.all([
    fetchScript(Number(route.params.id)),
    fetchCredentials(),
  ])
  script.value = sRes.data
  credentials.value = cRes.data
})

async function handleExecute() {
  running.value = true
  result.value = null
  try {
    const res = await executeScript(Number(route.params.id), selectedCredentials.value)
    result.value = res.data
  } catch (e: any) {
    result.value = { status: 'failed', exit_code: -1, log: e.message }
  } finally {
    running.value = false
  }
}
</script>
