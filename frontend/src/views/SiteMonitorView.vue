<template>
  <div>
    <n-space justify="space-between" style="margin-bottom: 16px">
      <n-h3 style="margin: 0">站点监控</n-h3>
      <n-space>
        <n-dropdown trigger="click" :options="exportOptions" @select="handleExport">
          <n-button><template #icon><n-icon><DownloadOutline /></n-icon></template>导出 SLA</n-button>
        </n-dropdown>
        <n-button type="primary" @click="openCreate">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          新建监控
        </n-button>
      </n-space>
    </n-space>

    <n-data-table :columns="columns" :data="monitors" :loading="loading" :row-key="(r: SiteMonitor) => r.id" />

    <!-- Create/Edit Modal -->
    <n-modal v-model:show="showForm" preset="card" :title="editingId ? '编辑监控' : '新建监控'" style="width: 560px">
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <n-form-item path="name" label="名称">
          <n-input v-model:value="form.name" placeholder="如: 官网首页" />
        </n-form-item>
        <n-form-item path="monitor_type" label="探测类型">
          <n-select v-model:value="form.monitor_type" :options="typeOptions" @update:value="onTypeChange" />
        </n-form-item>
        <n-form-item path="target" label="目标">
          <n-input v-model:value="form.target" :placeholder="form.monitor_type === 'http' ? 'https://example.com' : 'example.com:80'" />
        </n-form-item>
        <n-grid v-if="form.monitor_type === 'http'" :cols="2" :x-gap="16">
          <n-grid-item>
            <n-form-item path="http_method" label="HTTP 方法">
              <n-select v-model:value="form.http_method" :options="methodOptions" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item path="expected_status_codes" label="有效状态码">
              <n-input v-model:value="form.expected_status_codes" placeholder="200,301,302" />
            </n-form-item>
          </n-grid-item>
        </n-grid>
        <n-grid :cols="3" :x-gap="16">
          <n-grid-item>
            <n-form-item path="timeout" label="超时(秒)">
              <n-input-number v-model:value="form.timeout" :min="1" :max="60" style="width: 100%" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item path="retries" label="重试次数">
              <n-input-number v-model:value="form.retries" :min="0" :max="10" style="width: 100%" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item path="check_interval" label="间隔(秒)">
              <n-input-number v-model:value="form.check_interval" :min="30" :max="86400" style="width: 100%" />
            </n-form-item>
          </n-grid-item>
        </n-grid>
        <n-form-item path="alert_enabled" label="告警通知">
          <n-switch v-model:value="form.alert_enabled" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleSave">确认</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- History Drawer -->
    <n-drawer v-model:show="showHistory" :width="480">
      <n-drawer-content :title="`探测历史 — ${historyMonitorName}`" closable>
        <div v-if="historyLoading" style="text-align: center; padding: 20px">加载中...</div>
        <n-table v-else size="small">
          <thead>
            <tr><th>时间</th><th>状态</th><th>延迟</th><th style="width: 140px">详情</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in historyItems" :key="r.id">
              <td>{{ fmtTime(r.checked_at) }}</td>
              <td><n-tag :type="r.is_up ? 'success' : 'error'" size="small">{{ r.is_up ? 'UP' : 'DOWN' }}</n-tag></td>
              <td>{{ r.response_ms != null ? r.response_ms + ' ms' : '-' }}</td>
              <td style="max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
                {{ r.status_code != null ? 'HTTP ' + r.status_code : '' }}{{ r.error ? ' ' + r.error : '' }}
              </td>
            </tr>
          </tbody>
        </n-table>
        <n-pagination
          v-if="historyTotal > pageSize"
          style="margin-top: 12px; justify-content: center"
          :page="historyPage" :page-size="pageSize"
          :item-count="historyTotal"
          @update:page="(p: number) => { historyPage = p; loadHistory() }"
        />
      </n-drawer-content>
    </n-drawer>

    <!-- Heatmap Modal -->
    <n-modal v-model:show="showHeatmap" preset="card" :title="`${heatmapName} — 在线状态`" style="width: 680px">
      <n-space vertical :size="12">
        <n-radio-group v-model:value="heatmapModalDays" size="small" @update:value="loadHeatmapForModal">
          <n-radio-button :value="1">1天</n-radio-button>
          <n-radio-button :value="3">3天</n-radio-button>
          <n-radio-button :value="7">1周</n-radio-button>
          <n-radio-button :value="30">1月</n-radio-button>
        </n-radio-group>
        <div v-if="heatmapLoading" style="text-align: center; padding: 20px">加载中...</div>
        <div v-else-if="heatmapCells.length === 0" style="color: #999; text-align: center; padding: 20px">暂无数据</div>
        <div v-else class="heatmap-grid">
          <span
            v-for="(cell, i) in heatmapCells" :key="i"
            class="heatmap-dot"
            :style="`background: ${cell.is_up ? '#18a058' : '#d03050'}`"
            :title="`${cell.time} — ${cell.is_up ? 'UP' : 'DOWN'}`"
          />
        </div>
      </n-space>
    </n-modal>

  </div>
</template>

<script setup lang="ts">
import { h, ref, onMounted } from 'vue'
import { useMessage, useDialog, NTag, NButton, NIcon, NSpace, NDataTable, NModal, NForm, NFormItem, NInput, NInputNumber, NSelect, NSwitch, NH3, NGrid, NGridItem, NDrawer, NDrawerContent, NTable, NPagination, NDropdown, NRadioGroup, NRadioButton } from 'naive-ui'
import { AddOutline, PulseOutline, DownloadOutline, GridOutline } from '@vicons/ionicons5'
import {
  fetchSiteMonitors, createSiteMonitor, updateSiteMonitor, deleteSiteMonitor, checkNow, fetchHistory, exportSla, fetchHeatmap,
} from '@/api/site-monitors'
import type { SiteMonitor, SiteMonitorCreate, SiteCheckResult, HeatmapCell } from '@/api/site-monitors'

const message = useMessage()
const dialog = useDialog()

const monitors = ref<SiteMonitor[]>([])
const loading = ref(false)
const saving = ref(false)
const showForm = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref()
const form = ref<SiteMonitorCreate>({
  name: '', target: '', monitor_type: 'http', http_method: 'GET',
  expected_status_codes: '200', timeout: 10, retries: 2, check_interval: 300, alert_enabled: true,
})

const typeOptions = [{ label: 'HTTP(S)', value: 'http' }, { label: 'TCP', value: 'tcp' }]
const methodOptions = [{ label: 'GET', value: 'GET' }, { label: 'HEAD', value: 'HEAD' }]

const rules = {
  name: [{ required: true, message: '请输入名称' }],
  target: [{ required: true, message: '请输入目标' }],
}

function onTypeChange() {
  if (form.value.monitor_type === 'tcp') {
    form.value.http_method = 'GET'
    form.value.expected_status_codes = '200'
  }
}

// History state
const showHistory = ref(false)
const historyMonitorName = ref('')
const historyItems = ref<SiteCheckResult[]>([])
const historyTotal = ref(0)
const historyLoading = ref(false)
const historyPage = ref(1)
const historyMonitorId = ref(0)
const pageSize = 20

// Heatmap modal state
const showHeatmap = ref(false)
const heatmapName = ref('')
const heatmapCells = ref<HeatmapCell[]>([])
const heatmapLoading = ref(false)
const heatmapModalDays = ref(7)
const heatmapMonitorId = ref(0)

const exportOptions = [
  { label: '月度 SLA (CSV)', key: 'monthly' },
  { label: '年度 SLA (CSV)', key: 'annual' },
]

async function handleExport(key: string) {
  try {
    const resp = await exportSla(key)
    const blob = new Blob([resp.data as BlobPart], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `sla-${key}-report.csv`
    a.click()
    URL.revokeObjectURL(url)
    message.success('导出成功')
  } catch (_e) { message.error('导出失败') }
}

async function loadHeatmapForModal() {
  heatmapLoading.value = true
  try {
    const resp = await fetchHeatmap(heatmapMonitorId.value, heatmapModalDays.value)
    heatmapCells.value = resp.data
  } catch (_e) { /* ignore */ }
  finally { heatmapLoading.value = false }
}

function openHeatmap(row: SiteMonitor) {
  heatmapMonitorId.value = row.id
  heatmapName.value = row.name
  heatmapModalDays.value = 7
  heatmapCells.value = []
  showHeatmap.value = true
  loadHeatmapForModal()
}

async function loadMonitors() {
  loading.value = true
  try {
    const resp = await fetchSiteMonitors()
    monitors.value = resp.data
  } catch (_e) { /* ignore */ }
  finally { loading.value = false }
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', target: '', monitor_type: 'http', http_method: 'GET', expected_status_codes: '200', timeout: 10, retries: 2, check_interval: 300, alert_enabled: true }
  showForm.value = true
}

function openEdit(row: SiteMonitor) {
  editingId.value = row.id
  form.value = {
    name: row.name, target: row.target, monitor_type: row.monitor_type,
    http_method: row.http_method, expected_status_codes: row.expected_status_codes,
    timeout: row.timeout, retries: row.retries, check_interval: row.check_interval,
    alert_enabled: row.alert_enabled,
  }
  showForm.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editingId.value) {
      await updateSiteMonitor(editingId.value, form.value)
      message.success('更新成功')
    } else {
      await createSiteMonitor(form.value)
      message.success('创建成功')
    }
    showForm.value = false
    await loadMonitors()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally { saving.value = false }
}

function handleDelete(row: SiteMonitor) {
  dialog.warning({
    title: '确认删除', content: `确定要删除 "${row.name}" 吗？`, positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => {
      await deleteSiteMonitor(row.id)
      message.success('删除成功')
      await loadMonitors()
    },
  })
}

async function handleCheckNow(row: SiteMonitor) {
  try {
    const resp = await checkNow(row.id)
    const r = resp.data
    message.success(r.is_up ? `UP — ${r.response_ms} ms` : `DOWN — ${r.error || '连接失败'}`)
    await loadMonitors()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '检查失败')
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const resp = await fetchHistory(historyMonitorId.value, historyPage.value, pageSize)
    historyItems.value = resp.data.items
    historyTotal.value = resp.data.total
  } catch (_e) { /* ignore */ }
  finally { historyLoading.value = false }
}

function openHistory(row: SiteMonitor) {
  historyMonitorId.value = row.id
  historyMonitorName.value = row.name
  historyPage.value = 1
  showHistory.value = true
  loadHistory()
}

function fmtTime(val: string | null) {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const columns = [
  { title: '名称', key: 'name', width: 160, ellipsis: { tooltip: true } },
  {
    title: '类型', key: 'monitor_type', width: 80,
    render: (r: SiteMonitor) => h(NTag, { type: r.monitor_type === 'http' ? 'info' : 'success', size: 'small' }, () => r.monitor_type.toUpperCase()),
  },
  { title: '目标', key: 'target', width: 220, ellipsis: { tooltip: true } },
  {
    title: '状态', key: 'is_up', width: 80,
    render: (r: SiteMonitor) => h(NTag, { type: r.is_up ? 'success' : 'error', size: 'small' }, () => r.is_up ? 'UP' : 'DOWN'),
  },
  {
    title: '响应时间', key: 'last_response_ms', width: 100,
    render: (r: SiteMonitor) => r.last_response_ms != null ? `${r.last_response_ms} ms` : '-',
  },
  {
    title: '告警', key: 'alert_enabled', width: 70,
    render: (r: SiteMonitor) => h(NTag, { type: r.alert_enabled ? 'default' : 'default', size: 'small' }, () => r.alert_enabled ? '开' : '关'),
  },
  { title: '最后检查', key: 'last_checked_at', width: 150, render: (r: SiteMonitor) => fmtTime(r.last_checked_at) },
  {
    title: '在线状态', key: 'heatmap', width: 100,
    render: (row: SiteMonitor) => h(NButton, { size: 'tiny', quaternary: true, onClick: () => openHeatmap(row) },
      { icon: () => h(NIcon, null, () => h(GridOutline)), default: () => '热点图' }),
  },
  {
    title: '操作', key: 'actions', width: 200,
    render: (row: SiteMonitor) => h(NSpace, { size: 'small' }, () => [
      h(NButton, { size: 'tiny', type: 'primary', ghost: true, onClick: () => handleCheckNow(row) }, { icon: () => h(NIcon, null, () => h(PulseOutline)), default: () => '检查' }),
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => openHistory(row) }, () => '历史'),
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEdit(row) }, () => '编辑'),
      h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => handleDelete(row) }, () => '删除'),
    ]),
  },
]

onMounted(loadMonitors)
</script>

<style scoped>
.heatmap-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  max-height: 360px;
  overflow-y: auto;
  padding: 4px;
}
.heatmap-dot {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  flex-shrink: 0;
}
</style>
