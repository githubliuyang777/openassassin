<template>
  <div>
    <n-h3 style="margin-bottom: 16px">审计日志</n-h3>

    <n-space style="margin-bottom: 16px" align="end">
      <n-form-item label="用户" style="margin-bottom: 0">
        <n-input v-model:value="filters.username" placeholder="用户名" clearable style="width: 140px" @keyup.enter="loadPage(1)" />
      </n-form-item>
      <n-form-item label="操作" style="margin-bottom: 0">
        <n-select v-model:value="filters.action" :options="actionOptions" clearable style="width: 100px" />
      </n-form-item>
      <n-form-item label="开始日期" style="margin-bottom: 0">
        <n-date-picker v-model:formatted-value="filters.date_from" type="date" value-format="yyyy-MM-dd" style="width: 150px" />
      </n-form-item>
      <n-form-item label="结束日期" style="margin-bottom: 0">
        <n-date-picker v-model:formatted-value="filters.date_to" type="date" value-format="yyyy-MM-dd" style="width: 150px" />
      </n-form-item>
      <n-button @click="loadPage(1)" size="small" type="primary">查询</n-button>
      <n-button @click="resetFilters" size="small">重置</n-button>
    </n-space>

    <n-data-table
      :columns="columns"
      :data="logs"
      :loading="loading"
      :pagination="pagination"
      :row-key="(r: any) => r.id"
      size="small"
      @update:page="loadPage"
      @update:page-size="handlePageSizeChange"
    />
  </div>
</template>

<script setup lang="ts">
import { h, ref, onMounted, reactive } from 'vue'
import { useMessage, NTag, NButton, NSpace, NFormItem, NInput, NSelect, NDatePicker, NDataTable, NH3 } from 'naive-ui'
import { fetchAuditLogs } from '@/api/audit-logs'
import type { AuditLogEntry } from '@/api/audit-logs'
import type { DataTableColumn } from 'naive-ui'

const message = useMessage()

const logs = ref<AuditLogEntry[]>([])
const loading = ref(false)

const filters = reactive({
  username: '',
  action: null as string | null,
  date_from: null as string | null,
  date_to: null as string | null,
})

const actionOptions = [
  { label: 'POST', value: 'POST' },
  { label: 'PUT', value: 'PUT' },
  { label: 'PATCH', value: 'PATCH' },
  { label: 'DELETE', value: 'DELETE' },
]

const pagination = reactive({
  page: 1,
  pageSize: 50,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
})

function actionTag(action: string) {
  const colors: Record<string, string> = { POST: 'success', PUT: 'warning', PATCH: 'info', DELETE: 'error' }
  return h(NTag, { type: (colors[action] || 'default') as any, size: 'small' }, { default: () => action })
}

function statusTag(code: number) {
  if (code >= 200 && code < 300) return h(NTag, { type: 'success', size: 'small' }, { default: () => `${code}` })
  if (code >= 400) return h(NTag, { type: 'error', size: 'small' }, { default: () => `${code}` })
  return h(NTag, { type: 'default', size: 'small' }, { default: () => `${code}` })
}

const columns: DataTableColumn<AuditLogEntry>[] = [
  { title: '时间', key: 'created_at', width: 170, render: (r) => formatTime(r.created_at) },
  { title: '用户', key: 'username', width: 90 },
  { title: '操作', key: 'action', width: 70, render: (r) => actionTag(r.action) },
  { title: '资源', key: 'resource_type', width: 90, render: (r) => r.resource_type || '-' },
  { title: '详情', key: 'detail', width: 160, ellipsis: { tooltip: true }, render: (r) => r.detail || '-' },
  { title: '源IP', key: 'ip_address', width: 130, render: (r) => r.ip_address || '-' },
  { title: '归属地', key: 'ip_location', width: 120, ellipsis: { tooltip: true }, render: (r) => r.ip_location || '-' },
  { title: '状态码', key: 'status_code', width: 80, render: (r) => statusTag(r.status_code) },
]

function formatTime(val: string | null) {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

async function loadPage(page: number) {
  loading.value = true
  try {
    const params: Record<string, any> = { page, page_size: pagination.pageSize }
    if (filters.username) params.username = filters.username
    if (filters.action) params.action = filters.action
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to
    const resp = await fetchAuditLogs(params)
    logs.value = resp.data.items
    pagination.page = resp.data.page
    pagination.itemCount = resp.data.total
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function handlePageSizeChange(size: number) {
  pagination.pageSize = size
  loadPage(1)
}

function resetFilters() {
  filters.username = ''
  filters.action = null
  filters.date_from = null
  filters.date_to = null
  loadPage(1)
}

onMounted(() => loadPage(1))
</script>
