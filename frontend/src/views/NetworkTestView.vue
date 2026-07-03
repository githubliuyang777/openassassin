<template>
  <div>
    <n-h3 style="margin-bottom: 16px">网络测试</n-h3>

    <n-card title="TCP 连通性测试" style="max-width: 600px; margin-bottom: 24px">
      <n-form ref="formRef" :model="form" label-placement="top">
        <n-grid :cols="3" :x-gap="16">
          <n-grid-item :span="2">
            <n-form-item path="host" label="主机地址" :rule="{ required: true, message: '请输入 IP 或域名' }">
              <n-input v-model:value="form.host" placeholder="如: 192.168.1.1 或 example.com" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item path="port" label="端口" :rule="{ required: true, type: 'number', message: '请输入端口' }">
              <n-input-number v-model:value="form.port" :min="1" :max="65535" style="width: 100%" />
            </n-form-item>
          </n-grid-item>
        </n-grid>
        <n-form-item path="timeout" label="超时时间（秒）">
          <n-input-number v-model:value="form.timeout" :min="1" :max="30" :step="1" style="width: 120px" />
        </n-form-item>
      </n-form>
      <n-button type="primary" :loading="testing" @click="handleTest" style="margin-top: 8px">
        开始测试
      </n-button>
    </n-card>

    <div v-if="lastResult" style="margin-bottom: 24px">
      <n-card :bordered="true" :style="{ borderColor: lastResult.success ? '#18a058' : '#d03050' }">
        <template #header>
          <n-space align="center">
            <n-tag :type="lastResult.success ? 'success' : 'error'" size="medium">
              {{ lastResult.success ? '连通' : '不通' }}
            </n-tag>
            <n-text>{{ lastResult.host }}:{{ lastResult.port }}</n-text>
          </n-space>
        </template>
        <n-space vertical size="small">
          <div v-if="lastResult.success">
            <n-text depth="2">延迟：</n-text>
            <n-text strong>{{ lastResult.latency_ms }} ms</n-text>
          </div>
          <div v-if="lastResult.error">
            <n-text depth="2">错误：</n-text>
            <n-text type="error">{{ lastResult.error }}</n-text>
          </div>
        </n-space>
      </n-card>
    </div>

    <div v-if="history.length">
      <n-h4 style="margin-bottom: 8px">测试历史</n-h4>
      <n-data-table
        :columns="historyColumns"
        :data="history"
        :pagination="false"
        size="small"
        :max-height="300"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, ref } from 'vue'
import { useMessage, NTag, NButton, NIcon, NText, NSpace, NForm, NFormItem, NInput, NInputNumber, NH3, NH4, NCard, NDataTable, NGrid, NGridItem } from 'naive-ui'
import { testNetwork } from '@/api/network'
import type { NetworkTestResult } from '@/api/network'
import type { DataTableColumn } from 'naive-ui'

const message = useMessage()
const formRef = ref()

const form = ref({ host: '', port: 80, timeout: 5 })
const testing = ref(false)
const lastResult = ref<NetworkTestResult | null>(null)
const history = ref<NetworkTestResult[]>([])

const historyColumns: DataTableColumn<NetworkTestResult>[] = [
  { title: '主机', key: 'host', width: 200 },
  { title: '端口', key: 'port', width: 80 },
  { title: '结果', key: 'success', width: 90,
    render: (r) => h(NTag, { type: r.success ? 'success' : 'error', size: 'small' },
      { default: () => r.success ? '连通' : '不通' }),
  },
  { title: '延迟', key: 'latency_ms', width: 100, render: (r) => r.latency_ms !== null ? `${r.latency_ms} ms` : '-' },
  { title: '错误', key: 'error', width: 200, ellipsis: { tooltip: true }, render: (r) => r.error || '-' },
]

async function handleTest() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  testing.value = true
  try {
    const resp = await testNetwork(form.value)
    lastResult.value = resp.data
    history.value.unshift(resp.data)
    if (history.value.length > 20) history.value.pop()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '测试失败')
  } finally {
    testing.value = false
  }
}
</script>
