<template>
  <div>
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px">
      <n-h3 style="margin: 0">域名证书</n-h3>
      <n-space>
        <n-button v-if="isAdmin" @click="openPanelModal">
          <template #icon><n-icon><ServerOutline /></n-icon></template>
          宝塔面板
        </n-button>
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
      <n-divider vertical />
      <n-select v-model:value="selectedNotifGroup" :options="notifGroupOptions" placeholder="通知组" size="tiny" style="width: 160px" clearable />
      <n-button size="tiny" type="info" @click="handleBatchSetNotifGroup">设置通知组</n-button>
    </div>

    <n-data-table
      :columns="columns"
      :data="domains"
      :loading="loading"
      :pagination="false"
      size="small"
      :scroll-x="1900"
      :row-key="(row: any) => row.id"
      v-model:checked-row-keys="checkedRowKeys"
    />

    <!-- Add Domain Modal -->
    <n-modal v-model:show="showAddModal" preset="card" title="添加域名" style="width: 420px">
      <n-form :model="addForm" :rules="addRules" label-placement="top">
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

    <!-- Edit Domain Modal -->
    <n-modal v-model:show="showEditModal" preset="card" title="编辑域名" style="width: 580px">
      <n-form :model="editForm" label-placement="top">
        <n-form-item label="域名">
          <n-input :value="editForm.domain" disabled />
        </n-form-item>
        <n-form-item label="端口">
          <n-input-number v-model:value="editForm.port" :min="1" :max="65535" style="width: 100%" />
        </n-form-item>
        <n-form-item label="到期告警">
          <n-switch v-model:value="editForm.alert_enabled" />
        </n-form-item>
        <n-form-item label="通知组">
          <n-select v-model:value="editForm.notification_group_id" :options="notifGroupOptions" clearable placeholder="默认（管理员邮箱）" />
        </n-form-item>
        <n-divider style="margin: 8px 0" />
        <n-form-item label="证书维护平台">
          <n-space vertical style="width: 100%">
            <n-select v-model:value="editForm.cert_provider" :options="providerOptions" @update:value="onProviderChange" />
            <span style="font-size: 12px; color: #999">其它平台可通过后端 Provider 注册表扩展，无需修改域名表结构</span>
          </n-space>
        </n-form-item>
        <template v-if="editForm.cert_provider === 'baota'">
          <n-form-item label="宝塔面板">
            <n-select v-model:value="editForm.panel_id" :options="panelOptions" placeholder="选择宝塔面板" @update:value="onPanelChange" />
          </n-form-item>
          <n-form-item label="部署站点名（可选）">
            <n-space vertical style="width: 100%">
              <n-space>
                <n-select
                  v-model:value="editForm.site_name"
                  :options="siteOptions"
                  filterable
                  tag
                  clearable
                  placeholder="留空使用 ACME 订单域名"
                  style="min-width: 260px"
                />
                <n-button :loading="loadingSites" :disabled="!editForm.panel_id" @click="handleLoadSites">读取站点/订单</n-button>
              </n-space>
              <span style="font-size: 12px; color: #999">优先按 ACME 订单域名匹配；无订单时按该名称匹配宝塔站点</span>
            </n-space>
          </n-form-item>
          <n-form-item label="ACME 订单 ID（可选）">
            <n-input v-model:value="editForm.order_index" placeholder="留空自动匹配该域名最新的有效订单" />
          </n-form-item>
          <n-space>
            <n-form-item label="站点 ID（可选）">
              <n-input-number v-model:value="editForm.site_id" :min="1" placeholder="无订单时新申请需要" style="width: 180px" />
            </n-form-item>
            <n-form-item label="站点根目录（可选）">
              <n-input v-model:value="editForm.site_path" placeholder="/www/wwwroot/example.com" style="width: 280px" />
            </n-form-item>
          </n-space>
          <n-form-item label="自动续签">
            <n-switch v-model:value="editForm.cert_auto_renew" />
            <span style="font-size: 12px; color: #999; margin-left: 8px">证书进入到期告警阈值后自动触发</span>
          </n-form-item>
        </template>
        <div v-else style="font-size: 12px; color: #999; padding-left: 4px">
          该域名不通过本平台自动续签，仍保留证书到期监控。
        </div>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showEditModal = false">取消</n-button>
          <n-button type="primary" :loading="editSaving" @click="handleSaveEdit">保存</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Baota Panel Management Modal -->
    <n-modal v-model:show="showPanelModal" preset="card" title="宝塔面板管理" style="width: 820px">
      <n-space justify="space-between" align="center" style="margin-bottom: 12px">
        <span style="font-size: 12px; color: #999">面板需开启 API 接口并将本平台服务器 IP 加入白名单</span>
        <n-button size="small" type="primary" @click="openPanelCreate">添加面板</n-button>
      </n-space>
      <n-data-table :columns="panelColumns" :data="panels" :loading="panelLoading" :row-key="(r: BaotaPanel) => r.id" size="small" />
      <template v-if="showPanelForm">
        <n-divider />
        <n-form :model="panelForm" label-placement="top">
          <n-form-item label="名称">
            <n-input v-model:value="panelForm.name" placeholder="如：生产宝塔" />
          </n-form-item>
          <n-form-item label="面板地址">
            <n-input v-model:value="panelForm.panel_url" placeholder="https://1.2.3.4:8888" />
          </n-form-item>
          <n-form-item :label="editingPanelId ? 'API 密钥（留空不修改）' : 'API 密钥'">
            <n-input v-model:value="panelForm.api_key" type="password" show-password-on="click" placeholder="面板设置 → API 接口" />
          </n-form-item>
          <n-space>
            <n-form-item label="校验面板 TLS 证书">
              <n-switch v-model:value="panelForm.verify_tls" />
            </n-form-item>
            <n-form-item label="启用">
              <n-switch v-model:value="panelForm.enabled" />
            </n-form-item>
          </n-space>
          <div style="font-size: 12px; color: #999">自签证书面板可关闭 TLS 校验；HTTP 面板的 API 密钥可能被窃听，建议使用 HTTPS 或仅在内网访问。</div>
        </n-form>
      </template>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showPanelModal = false">关闭</n-button>
          <n-button v-if="showPanelForm" type="primary" :loading="panelSaving" @click="handleSavePanel">保存面板</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { useMessage, NTag, NButton, NIcon, NSpace, NDataTable, NModal, NForm, NFormItem, NInput, NInputNumber, NH3, NSwitch, NSelect, NDivider, useDialog } from 'naive-ui'
import { AddOutline, CloudUploadOutline, RefreshOutline, ServerOutline } from '@vicons/ionicons5'
import {
  fetchDomains, addDomain, batchImportDomains, refreshAllDomains, refreshDomain,
  deleteDomain, toggleDomainAlert, batchToggleDomainAlert, batchSetNotificationGroup,
  updateDomain, renewDomainCert,
} from '@/api/domains'
import { fetchGroups } from '@/api/notification-groups'
import { fetchBaotaPanels, createBaotaPanel, updateBaotaPanel, deleteBaotaPanel, testBaotaPanel } from '@/api/baota'
import { fetchCertProviders } from '@/api/cert-providers'
import { useAuthStore } from '@/stores/auth'
import type { DomainInfo, DomainUpdate } from '@/api/domains'
import type { BaotaPanel, BaotaPanelUpdate } from '@/api/baota'
import type { CertProvider } from '@/api/cert-providers'
import type { NotificationGroup } from '@/api/notification-groups'
import type { DataTableColumn } from 'naive-ui'

const message = useMessage()
const dialog = useDialog()
const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const domains = ref<DomainInfo[]>([])
const loading = ref(false)
const refreshing = ref(false)
const adding = ref(false)
const importing = ref(false)
const panels = ref<BaotaPanel[]>([])
const providers = ref<CertProvider[]>([])

const showAddModal = ref(false)
const addForm = ref({ domain: '', port: 443 })
const addRules = {
  domain: [{ required: true, message: '请输入域名' }],
  port: [{ required: true, type: 'number' as const, message: '请输入端口' }],
}

const showImportModal = ref(false)
const importText = ref('')
const checkedRowKeys = ref<number[]>([])
const selectedNotifGroup = ref<number | null>(null)
const notificationGroups = ref<NotificationGroup[]>([])
const notifGroupOptions = computed(() =>
  notificationGroups.value.map((g) => ({ label: g.name, value: g.id }))
)

const showEditModal = ref(false)
const editSaving = ref(false)
const loadingSites = ref(false)
const siteOptions = ref<{ label: string; value: string }[]>([])
const editForm = ref({
  id: 0,
  domain: '',
  port: 443,
  alert_enabled: true,
  notification_group_id: null as number | null,
  cert_provider: 'none',
  panel_id: null as number | null,
  site_name: '',
  order_index: '',
  site_id: null as number | null,
  site_path: '',
  cert_auto_renew: false,
})
const renewingIds = ref<number[]>([])
const renewTimers: Record<number, ReturnType<typeof setInterval>> = {}

function stopRenewPolling(id: number) {
  const timer = renewTimers[id]
  if (timer) {
    clearInterval(timer)
    delete renewTimers[id]
  }
}

const showPanelModal = ref(false)
const showPanelForm = ref(false)
const editingPanelId = ref<number | null>(null)
const panelSaving = ref(false)
const panelLoading = ref(false)
const panelForm = ref({ name: '', panel_url: '', api_key: '', verify_tls: true, enabled: true })

const panelOptions = computed(() =>
  panels.value.map((p) => ({ label: p.enabled ? p.name : `${p.name}（已禁用）`, value: p.id }))
)
const providerOptions = computed(() => [
  { label: '未接入', value: 'none' },
  ...providers.value.filter((p) => p.enabled).map((p) => ({ label: p.name, value: p.key })),
  { label: '其它平台（预留）', value: '__other__', disabled: true },
])

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

function providerLabel(row: DomainInfo) {
  if (!row.cert_provider || row.cert_provider === 'none') return '未接入'
  if (row.cert_provider === 'baota') {
    const panel = panels.value.find((p) => p.id === row.cert_provider_config?.panel_id)
    return panel ? `宝塔 · ${panel.name}` : '宝塔面板'
  }
  return row.cert_provider
}

function providerTag(row: DomainInfo) {
  const integrated = row.cert_provider && row.cert_provider !== 'none'
  return h(NTag, { type: integrated ? 'info' : 'default', size: 'small' }, () => providerLabel(row))
}

function renewStatusType(status: string): 'success' | 'error' | 'info' | 'warning' | 'default' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'pending') return 'info'
  if (status === 'skipped') return 'warning'
  return 'default'
}

function renewStatusTag(row: DomainInfo) {
  const labels: Record<string, string> = { pending: '进行中', success: '成功', failed: '失败', skipped: '跳过' }
  const title = row.last_renew_error || (row.last_renew_attempt_at ? `最近尝试: ${formatTime(row.last_renew_attempt_at)}` : '')
  return h(
    NTag,
    { type: renewStatusType(row.last_renew_status), size: 'small', title },
    () => labels[row.last_renew_status] || '未尝试',
  )
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
  { title: '维护平台', key: 'cert_provider', width: 130, render: providerTag },
  { title: '续签状态', key: 'last_renew_status', width: 110, render: renewStatusTag },
  { title: '告警', key: 'alert_enabled', width: 70,
    render: (row) => h(NSwitch, { size: 'small', value: row.alert_enabled, onUpdateValue: () => handleToggleAlert(row) }),
  },
  { title: '状态', key: 'ssl_expired', width: 90, render: (r) => statusTag(r) },
  { title: '检测时间', key: 'last_checked_at', width: 170, render: (r) => formatTime(r.last_checked_at) },
  {
    title: '操作', key: 'actions', width: 230,
    render: (row) => {
      const actions = [
        h(NButton, { size: 'small', quaternary: true, onClick: () => handleRefresh(row.id) },
          { icon: () => h(NIcon, null, () => h(RefreshOutline)) }),
      ]
      if (isAdmin.value) {
        actions.push(h(NButton, {
          size: 'small',
          quaternary: true,
          type: 'primary',
          loading: renewingIds.value.includes(row.id),
          disabled: row.cert_provider === 'none' || renewingIds.value.includes(row.id),
          onClick: () => handleRenew(row),
        }, { default: () => '续签' }))
        actions.push(h(NButton, { size: 'small', quaternary: true, onClick: () => openEdit(row) },
          { default: () => '编辑' }))
      }
      actions.push(h(NButton, { size: 'small', quaternary: true, type: 'error', onClick: () => handleDelete(row) },
        { default: () => '删除' }))
      return h(NSpace, { size: 'small' }, { default: () => actions })
    },
  },
]

const panelColumns: DataTableColumn<BaotaPanel>[] = [
  { title: '名称', key: 'name', width: 130, ellipsis: { tooltip: true } },
  { title: '面板地址', key: 'panel_url', ellipsis: { tooltip: true } },
  {
    title: '密钥', key: 'api_key_configured', width: 80,
    render: (r) => h(NTag, { type: r.api_key_configured ? 'success' : 'warning', size: 'small' }, () => r.api_key_configured ? '已配置' : '未配置'),
  },
  {
    title: '状态', key: 'enabled', width: 70,
    render: (r) => h(NTag, { type: r.enabled ? 'success' : 'default', size: 'small' }, () => r.enabled ? '启用' : '禁用'),
  },
  {
    title: '操作', key: 'actions', width: 170,
    render: (r) => h(NSpace, { size: 'small' }, () => [
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => handleTestPanel(r) }, () => '测试'),
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => openPanelEdit(r) }, () => '编辑'),
      h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => handleDeletePanel(r) }, () => '删除'),
    ]),
  },
]

async function loadMeta() {
  try {
    notificationGroups.value = (await fetchGroups()).data
  } catch (_e) { /* ignore */ }
  try {
    const [panelResp, providerResp] = await Promise.all([fetchBaotaPanels(), fetchCertProviders()])
    panels.value = panelResp.data
    providers.value = providerResp.data
  } catch (_e) {
    // 非管理员无法读取面板详情，但平台列表仍用于表单展示
    try { providers.value = (await fetchCertProviders()).data } catch (_e2) { /* ignore */ }
  }
}

async function loadDomains(silent = false) {
  if (!silent) loading.value = true
  try {
    domains.value = (await fetchDomains()).data
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    if (!silent) loading.value = false
  }
}

async function handleAdd() {
  if (!addForm.value.domain.trim()) {
    message.warning('请输入域名')
    return
  }
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

async function handleBatchSetNotifGroup() {
  try {
    const resp = await batchSetNotificationGroup(checkedRowKeys.value, selectedNotifGroup.value ?? null)
    await loadDomains()
    checkedRowKeys.value = []
    message.success(`已更新 ${resp.data.updated} 个域名的通知组`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  }
}

function openEdit(row: DomainInfo) {
  const config = row.cert_provider_config || {}
  editForm.value = {
    id: row.id,
    domain: row.domain,
    port: row.port,
    alert_enabled: row.alert_enabled,
    notification_group_id: row.notification_group_id ?? null,
    cert_provider: row.cert_provider || 'none',
    panel_id: config.panel_id ?? null,
    site_name: config.site_name || '',
    order_index: config.order_index || '',
    site_id: config.site_id ?? null,
    site_path: config.site_path || '',
    cert_auto_renew: row.cert_auto_renew,
  }
  siteOptions.value = config.site_name ? [{ label: config.site_name, value: config.site_name }] : []
  showEditModal.value = true
}

function onProviderChange(value: string) {
  if (value !== 'baota') {
    editForm.value.panel_id = null
    editForm.value.site_name = ''
    editForm.value.cert_auto_renew = false
    siteOptions.value = []
  }
}

function onPanelChange() {
  editForm.value.site_name = ''
  siteOptions.value = []
}

async function handleLoadSites() {
  if (!editForm.value.panel_id) return
  loadingSites.value = true
  try {
    const resp = await testBaotaPanel(editForm.value.panel_id)
    const sites = resp.data.sites || []
    const orders = resp.data.orders || []
    if (sites.length) {
      siteOptions.value = sites.map((s) => ({ label: s.name, value: s.name }))
    } else if (orders.length) {
      const domains = Array.from(new Set(orders.flatMap((o) => o.domains)))
      siteOptions.value = domains.map((d) => ({ label: d, value: d }))
    } else {
      siteOptions.value = []
    }
    message.success(resp.data.message || `读取到 ${sites.length} 个站点`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.message || '读取站点失败')
  } finally {
    loadingSites.value = false
  }
}

async function handleSaveEdit() {
  if (editForm.value.cert_provider === 'baota' && !editForm.value.panel_id) {
    message.warning('请选择宝塔面板')
    return
  }
  editSaving.value = true
  try {
    const payload: DomainUpdate = {
      port: editForm.value.port,
      alert_enabled: editForm.value.alert_enabled,
      notification_group_id: editForm.value.notification_group_id,
      cert_provider: editForm.value.cert_provider,
      cert_provider_config: editForm.value.cert_provider === 'baota'
        ? {
            panel_id: editForm.value.panel_id!,
            site_name: (editForm.value.site_name || '').trim(),
            order_index: (editForm.value.order_index || '').trim(),
            site_id: editForm.value.site_id,
            site_path: (editForm.value.site_path || '').trim(),
          }
        : {},
      cert_auto_renew: editForm.value.cert_provider === 'baota' ? editForm.value.cert_auto_renew : false,
    }
    await updateDomain(editForm.value.id, payload)
    message.success('保存成功')
    showEditModal.value = false
    await loadDomains()
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.message || '保存失败')
  } finally {
    editSaving.value = false
  }
}

async function handleRenew(row: DomainInfo) {
  const beforeAttempt = row.last_renew_attempt_at
  try {
    await renewDomainCert(row.id)
    message.info('已开始续签，请稍候')
    stopRenewPolling(row.id)
    if (!renewingIds.value.includes(row.id)) {
      renewingIds.value = [...renewingIds.value, row.id]
    }
    const started = Date.now()
    renewTimers[row.id] = setInterval(async () => {
      await loadDomains(true)
      const current = domains.value.find((d) => d.id === row.id)
      const changed = current && current.last_renew_attempt_at !== beforeAttempt && current.last_renew_status !== 'pending'
      if (changed || Date.now() - started > 300000) {
        stopRenewPolling(row.id)
        renewingIds.value = renewingIds.value.filter((id) => id !== row.id)
        if (current?.last_renew_status === 'success') {
          message.success('证书续签成功')
        } else if (current?.last_renew_status === 'failed') {
          message.error(current.last_renew_error || '证书续签失败')
        } else if (current?.last_renew_status === 'skipped') {
          message.warning(current.last_renew_error || '续签已跳过')
        } else if (!changed) {
          message.warning('续签仍在后台进行，请稍后刷新')
        }
      }
    }, 3000)
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.message || '续签失败')
  }
}

function openPanelModal() {
  showPanelModal.value = true
  showPanelForm.value = false
  void loadMeta()
}

function openPanelCreate() {
  editingPanelId.value = null
  panelForm.value = { name: '', panel_url: '', api_key: '', verify_tls: true, enabled: true }
  showPanelForm.value = true
}

function openPanelEdit(panel: BaotaPanel) {
  editingPanelId.value = panel.id
  panelForm.value = {
    name: panel.name,
    panel_url: panel.panel_url,
    api_key: '',
    verify_tls: panel.verify_tls,
    enabled: panel.enabled,
  }
  showPanelForm.value = true
}

async function handleSavePanel() {
  if (!panelForm.value.name.trim() || !panelForm.value.panel_url.trim()) {
    message.warning('请填写面板名称和地址')
    return
  }
  if (!editingPanelId.value && !panelForm.value.api_key.trim()) {
    message.warning('请填写 API 密钥')
    return
  }
  panelSaving.value = true
  try {
    if (editingPanelId.value) {
      const payload: BaotaPanelUpdate = {
        name: panelForm.value.name.trim(),
        panel_url: panelForm.value.panel_url.trim(),
        verify_tls: panelForm.value.verify_tls,
        enabled: panelForm.value.enabled,
      }
      if (panelForm.value.api_key.trim()) payload.api_key = panelForm.value.api_key.trim()
      await updateBaotaPanel(editingPanelId.value, payload)
    } else {
      await createBaotaPanel({
        name: panelForm.value.name.trim(),
        panel_url: panelForm.value.panel_url.trim(),
        api_key: panelForm.value.api_key.trim(),
        verify_tls: panelForm.value.verify_tls,
        enabled: panelForm.value.enabled,
      })
    }
    message.success('保存成功')
    showPanelForm.value = false
    await loadMeta()
    await loadDomains(true)
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.message || '保存失败')
  } finally {
    panelSaving.value = false
  }
}

function handleDeletePanel(panel: BaotaPanel) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除宝塔面板 "${panel.name}" 吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteBaotaPanel(panel.id)
        message.success('删除成功')
        await loadMeta()
        await loadDomains(true)
      } catch (e: any) {
        message.error(e.response?.data?.detail || e.message || '删除失败')
      }
    },
  })
}

async function handleTestPanel(panel: BaotaPanel) {
  try {
    const resp = await testBaotaPanel(panel.id)
    message.success(resp.data.message || `连接成功，共 ${resp.data.sites.length} 个站点`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.message || '连接失败')
  }
}

onMounted(async () => {
  if (!auth.user) {
    try { await auth.fetchMe() } catch (_e) { /* ignore */ }
  }
  loadMeta()
  loadDomains()
})

onUnmounted(() => {
  Object.keys(renewTimers).forEach((id) => stopRenewPolling(Number(id)))
})
</script>
