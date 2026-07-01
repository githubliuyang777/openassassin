<template>
  <div>
    <n-h3 style="margin-bottom: 16px">执行历史</n-h3>

    <n-data-table :columns="columns" :data="executions" :loading="loading" :row-key="(r: any) => r.id"
      :pagination="{ page: page, pageSize: pageSize, itemCount: total, onChange: onPageChange }" />

    <n-modal v-model:show="showLog" title="执行日志" style="width: 800px">
      <n-log v-if="log" :log="log" :rows="24" language="log" style="font-family: monospace; font-size: 13px" />
      <n-skeleton v-else :repeat="6" />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import { NH3, NDataTable, NModal, NButton, NTag, NLog, NSkeleton, NSpace } from 'naive-ui'
import { fetchExecutions, fetchExecutionLog, type Execution } from '@/api/executions'

const executions = ref<Execution[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showLog = ref(false)
const log = ref('')

type TagType = 'success' | 'error' | 'warning' | 'info' | 'default' | 'primary'
const statusColors: Record<string, TagType> = {
  success: 'success', failed: 'error', timeout: 'warning', running: 'info', pending: 'default',
}

const columns: any[] = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '脚本ID', key: 'script_id', width: 80 },
  { title: '状态', key: 'status', width: 80,
    render: (r: any) => h(NTag, { type: statusColors[r.status] || 'default', size: 'small' }, () => r.status),
  },
  { title: '退出码', key: 'exit_code', width: 70 },
  { title: '触发者', key: 'triggered_by', width: 80 },
  { title: '开始时间', key: 'started_at', width: 170 },
  {
    title: '操作', key: 'actions', width: 100,
    render: (r: any) => h(NSpace, null, () => [
      h(NButton, { size: 'small', onClick: () => handleViewLog(r.id) }, () => '日志'),
    ]),
  },
]

async function load() {
  loading.value = true
  try {
    const res = await fetchExecutions(page.value, pageSize.value)
    executions.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  page.value = p
  load()
}

async function handleViewLog(id: number) {
  showLog.value = true
  log.value = ''
  try {
    const res = await fetchExecutionLog(id)
    log.value = res.data.log
  } catch {
    log.value = '(日志加载失败)'
  }
}

onMounted(load)
</script>
