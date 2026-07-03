<template>
  <div>
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px">
      <n-h3 style="margin: 0">域名证书</n-h3>
      <n-space>
        <n-button @click="showAddModal = true">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          添加域名
        </n-button>
        <n-button @click="showImportModal = true">
          <template #icon><n-icon><CloudUploadOutline /></n-icon></template>
          批量导入
        </n-button>
        <n-button :loading="refreshing" @click="handleRefreshAll">
          <template #icon><n-icon><RefreshOutline /></n-icon></template>
          刷新全部
        </n-button>
      </n-space>
    </div>

    <div v-if="checkedRowKeys.length" style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding: 8px 16px; background: #f0f9eb; border-radius: 8px; border: 1px solid #b9e6a0">
      <span style="font-size: 13px; color: #3c6e1f">已选 {{ checkedRowKeys.length }} 项</span>
      <n-button size="tiny" @click="checkedRowKeys = domains.map(d => d.id)">全选</n-button>
      <n-button size="tiny" @click="checkedRowKeys = []">取消选择</n-button>
      <n-button size="tiny" type="primary" @click="handleBatchToggleAlert(true)">启用告警</n-button>
      <n-button size="tiny" type="warning" @click="handleBatchToggleAlert(false)">停用告警</n-button>
    </div>

    <n-data-table
      :columns="columns"
      :data="domains"
      :loading="loading"
      :pagination="false"
      size="small"
      :row-key="(row: any) => row.id"
      v-model:checked-row-keys="checkedRowKeys"
    />

    <!-- Add Domain Modal -->
    <n-modal v-model:show="showAddModal" preset="card" title="添加域名" style="width: 420px">
      <n-form ref="addFormRef" :model="addForm" :rules="addRules" label-placement="top">
        <n-form-item path="domain" label="域名">
          <n-input v-model:value="addForm.domain" placeholder="example.com" />
        </n-form-item>
        <n-form-item path="port" label="端口">
          <n-input-number v-model:value="addForm.port" :min="1" :max="65535" style="width: 100%" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showAddModal = false">取消</n-button>
          <n-button type="primary" :loading="adding" @click="handleAdd">确认添加</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Batch Import Modal -->
    <n-modal v-model:show="showImportModal" preset="card" title="批量导入域名" style="width: 520px">
      <n-form label-placement="top">
        <n-form-item label="域名列表（每行一个，支持 domain:port 格式）">
          <n-input
            v-model:value="importText"
            type="textarea"
            :rows="8"
            placeholder="example.com&#10;api.example.com:8443&#10;www.example.com"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showImportModal = false">取消</n-button>
          <n-button type="primary" :loading="importing" @click="handleBatchImport">确认导入</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { h, ref, onMounted, computed } from 'vue'
import { useMessage, NTag, NButton, NIcon, NSpace, NDataTable, NModal, NForm, NFormItem, NInput, NInputNumber, NH3, NSwitch, useDialog } from 'naive-ui'
import { AddOutline, CloudUploadOutline, RefreshOutline } from '@vicons/ionicons5'
import { fetchDomains, addDomain, batchImportDomains, refreshAllDomains, refreshDomain, deleteDomain, toggleDomainAlert, batchToggleDomainAlert } from '@/api/domains'
import type { DomainInfo } from '@/api/domains'
import type { DataTableColumn } from 'naive-ui'

const message = useMessage()
const dialog = useDialog()

const domains = ref<DomainInfo[]>([])
const loading = ref(false)
const refreshing = ref(false)
const adding = ref(false)
const importing = ref(false)

const showAddModal = ref(false)
const addForm = ref({ domain: '', port: 443 })
const addFormRef = ref()
const addRules = {
  domain: [{ required: true, message: '请输入域名' }],
  port: [{ required: true, type: 'number' as const, message: '请输入端口' }],
}

const showImportModal = ref(false)
const importText = ref('')
const checkedRowKeys = ref<number[]>([])

function statusTag(info: DomainInfo) {
  if (info.ssl_not_after === null) {
    return h(NTag, { type: 'default', size: 'small' }, { default: () => '未检测' })
  }
  if (info.ssl_expired) {
    return h(NTag, { type: 'error', size: 'small' }, { default: () => '已过期' })
  }
  if (info.days_remaining !== null && info.days_remaining <= 30) {
    return h(NTag, { type: 'warning', size: 'small' }, { default: () => '即将过期' })
  }
  return h(NTag, { type: 'success', size: 'small' }, { default: () => '有效' })
}

function formatTime(val: string | null) {
  if (!val) return '-'
  const d = new Date(val)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function daysRemaining(info: DomainInfo) {
  if (info.days_remaining === null) return '-'
  if (info.days_remaining < 0) return `${Math.abs(info.days_remaining)}天前`
  return `${info.days_remaining} 天`
}

const columns: DataTableColumn<DomainInfo>[] = [
  { type: 'selection' as const },
  { title: '域名', key: 'domain', width: 200, ellipsis: { tooltip: true } },
  { title: '端口', key: 'port', width: 70 },
  { title: '证书主题', key: 'ssl_subject', width: 200, ellipsis: { tooltip: true }, render: (r) => r.ssl_subject || '-' },
  { title: '颁发者', key: 'ssl_issuer', width: 180, ellipsis: { tooltip: true }, render: (r) => r.ssl_issuer || '-' },
  { title: '生效时间', key: 'ssl_not_before', width: 170, render: (r) => formatTime(r.ssl_not_before) },
  { title: '过期时间', key: 'ssl_not_after', width: 170, render: (r) => formatTime(r.ssl_not_after) },
  { title: '剩余', key: 'days_remaining', width: 80, render: (r) => daysRemaining(r) },
  { title: '告警', key: 'alert_enabled', width: 70,
    render: (row) => h(NSwitch, { size: 'small', value: row.alert_enabled, onUpdateValue: () => handleToggleAlert(row) }),
  },
  { title: '状态', key: 'ssl_expired', width: 90, render: (r) => statusTag(r) },
  { title: '检测时间', key: 'last_checked_at', width: 170, render: (r) => formatTime(r.last_checked_at) },
  {
    title: '操作', key: 'actions', width: 140,
    render: (row) => h(NSpace, { size: 'small' }, {
      default: () => [
        h(NButton, { size: 'small', quaternary: true, onClick: () => handleRefresh(row.id) },
          { icon: () => h(NIcon, null, () => h(RefreshOutline)) }),
        h(NButton, { size: 'small', quaternary: true, type: 'error', onClick: () => handleDelete(row) },
          { default: () => '删除' }),
      ],
    }),
  },
]

async function loadDomains() {
  loading.value = true
  try {
    const resp = await fetchDomains()
    domains.value = resp.data
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function handleAdd() {
  const valid = await addFormRef.value?.validate().catch(() => false)
  if (!valid) return
  adding.value = true
  try {
    await addDomain(addForm.value.domain, addForm.value.port)
    message.success('添加成功')
    showAddModal.value = false
    addForm.value = { domain: '', port: 443 }
    await loadDomains()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '添加失败')
  } finally {
    adding.value = false
  }
}

async function handleBatchImport() {
  const lines = importText.value.split('\n').map(s => s.trim()).filter(s => s)
  if (!lines.length) {
    message.warning('请输入至少一个域名')
    return
  }
  importing.value = true
  try {
    const resp = await batchImportDomains(lines)
    const r = resp.data.result
    message.success(`导入完成：新增 ${r.added}，跳过 ${r.skipped}，无效 ${r.invalid}`)
    showImportModal.value = false
    importText.value = ''
    domains.value = resp.data.domains
  } catch (e: any) {
    message.error(e.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

async function handleRefreshAll() {
  refreshing.value = true
  try {
    const resp = await refreshAllDomains()
    domains.value = resp.data.domains
    message.success(`已刷新 ${resp.data.refreshed} 个域名`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '刷新失败')
  } finally {
    refreshing.value = false
  }
}

async function handleRefresh(id: number) {
  try {
    await refreshDomain(id)
    message.success('刷新成功')
    await loadDomains()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '刷新失败')
  }
}

function handleDelete(row: DomainInfo) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除域名 "${row.domain}" 吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteDomain(row.id)
        message.success('删除成功')
        await loadDomains()
      } catch (e: any) {
        message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

async function handleToggleAlert(row: DomainInfo) {
  try {
    await toggleDomainAlert(row.id)
    await loadDomains()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleBatchToggleAlert(enabled: boolean) {
  try {
    const resp = await batchToggleDomainAlert(checkedRowKeys.value, enabled)
    domains.value = resp.data.domains
    checkedRowKeys.value = []
    message.success(`已${enabled ? '启用' : '停用'} ${resp.data.updated} 个域名的告警`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  }
}

onMounted(loadDomains)
</script>
