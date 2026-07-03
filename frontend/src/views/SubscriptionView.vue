<template>
  <div>
    <n-space justify="space-between" style="margin-bottom: 16px">
      <n-h3 style="margin: 0">订阅</n-h3>
      <n-button type="primary" @click="openCreate">
        <template #icon><n-icon><AddOutline /></n-icon></template>
        新建订阅
      </n-button>
    </n-space>

    <n-data-table :columns="columns" :data="subs" :loading="loading" :row-key="(r: any) => r.id" />

    <n-modal v-model:show="showForm" preset="card" :title="editingId ? '编辑订阅' : '新建订阅'" style="width: 520px">
      <n-form ref="formRef" :model="form" :rules="formRules" label-placement="top">
        <n-form-item path="name" label="组件名称">
          <n-input v-model:value="form.name" placeholder="如: nginx" />
        </n-form-item>
        <n-form-item path="repo_url" label="GitHub 仓库地址">
          <n-input v-model:value="form.repo_url" placeholder="https://github.com/nginx/nginx" @blur="handleLookup" />
        </n-form-item>
        <n-grid :cols="3" :x-gap="12">
          <n-grid-item>
            <n-form-item path="repo_platform" label="平台">
              <n-input v-model:value="form.repo_platform" disabled />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item path="repo_owner" label="Owner">
              <n-input v-model:value="form.repo_owner" disabled />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item path="repo_name" label="Repo">
              <n-input v-model:value="form.repo_name" disabled />
            </n-form-item>
          </n-grid-item>
        </n-grid>
        <div v-if="lookupResult.description" style="margin-bottom: 8px; font-size: 12px; color: #666">
          {{ lookupResult.description }}
        </div>
        <div v-if="lookupResult.latest_version" style="font-size: 12px; color: #18a058">
          当前最新版本: {{ lookupResult.latest_version }}
        </div>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleSave">确认</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-modal v-model:show="showAlerts" preset="card" title="新动态" style="width: 640px; max-height: 80vh">
      <div v-if="alerts.length === 0" style="color: #999; text-align: center; padding: 24px 0">暂无新动态</div>
      <n-list v-else>
        <n-list-item v-for="a in alerts" :key="a.id">
          <n-space vertical :size="4" style="width: 100%">
            <n-space align="center">
              <n-tag :type="a.alert_type === 'release' ? 'success' : 'error'" size="small">
                {{ a.alert_type === 'release' ? '新版本' : '漏洞' }}
              </n-tag>
              <n-text strong>{{ a.title }}</n-text>
              <n-tag v-if="a.is_read" size="small" type="default">已读</n-tag>
            </n-space>
            <n-text depth="2" style="font-size: 13px; white-space: pre-wrap">{{ a.summary || '暂无摘要' }}</n-text>
            <n-space size="small">
              <n-button v-if="a.url" text size="tiny" type="primary" @click="openUrl(a.url)">查看详情</n-button>
              <n-button v-if="!a.is_read" text size="tiny" @click="handleMarkRead(a.id)">标记已读</n-button>
            </n-space>
          </n-space>
        </n-list-item>
      </n-list>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { h, ref, reactive, onMounted } from 'vue'
import { useMessage, NTag, NButton, NIcon, NText, NSpace, NForm, NFormItem, NInput, NSelect, NH3, NDataTable, NModal, NGrid, NGridItem, NList, NListItem, useDialog } from 'naive-ui'
import { AddOutline } from '@vicons/ionicons5'
import { fetchSubscriptions, createSubscription, updateSubscription, deleteSubscription, fetchAlerts, markAlertRead, lookupRepo } from '@/api/subscriptions'
import type { Subscription, SubscriptionCreate, SubscriptionAlert, RepoLookupResult } from '@/api/subscriptions'
import type { DataTableColumn } from 'naive-ui'

const message = useMessage()
const dialog = useDialog()

const subs = ref<Subscription[]>([])
const loading = ref(false)
const saving = ref(false)
const showForm = ref(false)
const showAlerts = ref(false)
const editingId = ref<number | null>(null)

const form = ref<SubscriptionCreate>({ name: '', repo_url: '', repo_platform: 'github', repo_owner: '', repo_name: '' })
const formRef = ref()
const formRules = {
  name: [{ required: true, message: '请输入组件名称' }],
  repo_url: [{ required: true, message: '请输入仓库地址' }],
}

const lookupResult = ref<RepoLookupResult>({ repo_owner: '', repo_name: '', repo_platform: '', description: '', latest_version: '' })
const alerts = ref<SubscriptionAlert[]>([])

const columns: DataTableColumn<Subscription>[] = [
  { title: '组件', key: 'name', width: 130 },
  { title: '仓库', key: 'repo_url', width: 200, ellipsis: { tooltip: true } },
  { title: '最新版本', key: 'last_version', width: 110, render: (r) => r.last_version || '-' },
  { title: '上次检查', key: 'last_checked_at', width: 160, render: (r) => formatTime(r.last_checked_at) },
  { title: '新动态', key: 'alert_count', width: 80,
    render: (r) => r.alert_count > 0
      ? h(NTag, { type: 'warning', size: 'small' }, { default: () => `${r.alert_count}` })
      : h(NText, { depth: 3 }, { default: () => '-' }),
  },
  {
    title: '操作', key: 'actions', width: 180,
    render: (row) => h(NSpace, { size: 'small' }, {
      default: () => [
        h(NButton, { size: 'small', quaternary: true, onClick: () => handleShowAlerts(row) }, { default: () => '新动态' }),
        h(NButton, { size: 'small', quaternary: true, onClick: () => handleEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', quaternary: true, type: 'error', onClick: () => handleDelete(row) }, { default: () => '删除' }),
      ],
    }),
  },
]

function formatTime(val: string | null) {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

async function loadSubs() {
  loading.value = true
  try {
    subs.value = (await fetchSubscriptions()).data
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally { loading.value = false }
}

async function handleLookup() {
  const url = form.value.repo_url.trim()
  if (!url.startsWith('https://github.com/')) return
  try {
    lookupResult.value = (await lookupRepo(url)).data
    form.value.repo_owner = lookupResult.value.repo_owner
    form.value.repo_name = lookupResult.value.repo_name
    form.value.repo_platform = lookupResult.value.repo_platform
  } catch (_e) { /* ignore */ }
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', repo_url: '', repo_platform: 'github', repo_owner: '', repo_name: '' }
  lookupResult.value = { repo_owner: '', repo_name: '', repo_platform: '', description: '', latest_version: '' }
  showForm.value = true
}

function handleEdit(row: Subscription) {
  editingId.value = row.id
  form.value = { name: row.name, repo_url: row.repo_url, repo_platform: row.repo_platform, repo_owner: row.repo_owner, repo_name: row.repo_name }
  showForm.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editingId.value) {
      await updateSubscription(editingId.value, form.value)
      message.success('更新成功')
    } else {
      await createSubscription(form.value)
      message.success('创建成功')
    }
    showForm.value = false
    await loadSubs()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally { saving.value = false }
}

function handleDelete(row: Subscription) {
  dialog.warning({
    title: '确认删除', content: `确定要删除 "${row.name}" 的订阅吗？`, positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteSubscription(row.id)
        message.success('删除成功')
        await loadSubs()
      } catch (e: any) { message.error(e.response?.data?.detail || '删除失败') }
    },
  })
}

async function handleShowAlerts(row: Subscription) {
  try {
    alerts.value = (await fetchAlerts(row.id)).data
    showAlerts.value = true
  } catch (e: any) { message.error(e.response?.data?.detail || '加载失败') }
}

function openUrl(url: string) {
  window.open(url, '_blank')
}

async function handleMarkRead(alertId: number) {
  try {
    await markAlertRead(alertId)
    const a = alerts.value.find(x => x.id === alertId)
    if (a) { a.is_read = true }
    await loadSubs()
  } catch (_e) { /* ignore */ }
}

onMounted(loadSubs)
</script>
