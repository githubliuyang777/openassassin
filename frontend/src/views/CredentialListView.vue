<template>
  <div>
    <n-space justify="space-between" style="margin-bottom: 16px">
      <n-h3 style="margin: 0">密钥管理</n-h3>
      <n-button type="primary" @click="showCreate = true">
        <template #icon><n-icon><AddOutline /></n-icon></template>
        新建密钥
      </n-button>
    </n-space>

    <n-data-table :columns="columns" :data="credentials" :loading="loading" :row-key="(r: any) => r.id" />

    <n-modal v-model:show="showCreate" preset="card" title="新建密钥" style="width: 520px">
      <n-form ref="createFormRef" :model="createForm" :rules="createRules" label-placement="top">
        <n-form-item path="name" label="名称">
          <n-input v-model:value="createForm.name" placeholder="如: K8s 集群 Token" />
        </n-form-item>
        <n-grid :cols="2" :x-gap="16">
          <n-grid-item>
            <n-form-item path="type" label="类型">
              <n-select v-model:value="createForm.type" :options="typeOptions" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item path="key" label="环境变量名">
              <n-input v-model:value="createForm.key" placeholder="如: K8S_TOKEN" />
            </n-form-item>
          </n-grid-item>
        </n-grid>
        <n-form-item path="value" label="密钥值">
          <n-input type="textarea" v-model:value="createForm.value" placeholder="密钥内容" :rows="4" />
        </n-form-item>
        <n-form-item path="expires_at" label="截止有效期">
          <n-date-picker v-model:formatted-value="createForm.expires_at" type="date"
            value-format="yyyy-MM-dd'T'HH:mm:ss" style="width: 100%" placeholder="选填，过期后可用于告警" />
        </n-form-item>
        <n-form-item path="description" label="描述">
          <n-input v-model:value="createForm.description" placeholder="用途说明" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showCreate = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleCreate">保存</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-modal v-model:show="showReveal" title="查看密钥">
      <n-descriptions v-if="revealed" :columns="1" label-placement="left">
        <n-descriptions-item label="名称">{{ revealed.name }}</n-descriptions-item>
        <n-descriptions-item label="类型">{{ getTypeLabel(revealed.type) }}</n-descriptions-item>
        <n-descriptions-item label="环境变量">${{ revealed.key }}</n-descriptions-item>
        <n-descriptions-item label="值">
          <n-text code>{{ revealed.value }}</n-text>
        </n-descriptions-item>
        <n-descriptions-item v-if="revealed.expires_at" label="有效期">
          {{ revealed.expires_at }}
        </n-descriptions-item>
      </n-descriptions>
    </n-modal>

    <n-modal v-model:show="showDelete" preset="card" title="确认删除" style="width: 400px">
      <p>确定要删除密钥 "{{ deleting?.name }}" 吗？</p>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showDelete = false">取消</n-button>
          <n-button type="error" :loading="deleting_loading" @click="confirmDelete">删除</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, computed, onMounted } from 'vue'
import {
  NH3, NSpace, NButton, NIcon, NDataTable, NModal, NForm, NFormItem,
  NInput, NSelect, NDatePicker, NGrid, NGridItem,
  NDescriptions, NDescriptionsItem, NText, NTag, useMessage,
} from 'naive-ui'
import { AddOutline, AlertCircleOutline } from '@vicons/ionicons5'
import {
  fetchCredentials, createCredential, revealCredential, deleteCredential,
  type Credential, type CredentialReveal, CREDENTIAL_TYPES, getTypeLabel,
} from '@/api/credentials'

const message = useMessage()

const credentials = ref<Credential[]>([])
const loading = ref(false)
const showCreate = ref(false)
const showReveal = ref(false)
const showDelete = ref(false)
const saving = ref(false)
const deleting_loading = ref(false)
const deleting = ref<Credential | null>(null)
const revealed = ref<CredentialReveal | null>(null)

const typeOptions = CREDENTIAL_TYPES.map(t => ({ label: t.label, value: t.value }))

const createForm = ref({
  name: '', key: '', value: '', description: '',
  type: 'generic', expires_at: null as string | null,
})
const createFormRef = ref()
const createRules = {
  name: [{ required: true, message: '请输入名称' }],
  key: [{ required: true, message: '请输入环境变量名' }],
  value: [{ required: true, message: '请输入密钥值' }],
}

function daysLeft(expiresAt: string | null): number | null {
  if (!expiresAt) return null
  const now = Date.now()
  const exp = new Date(expiresAt).getTime()
  return Math.ceil((exp - now) / (1000 * 60 * 60 * 24))
}

type TagColor = 'warning' | 'error' | 'info' | 'default'
function typeColor(type: string): TagColor {
  const colors: Record<string, TagColor> = {
    kubeconfig: 'warning',
    tls_cert: 'error',
    api_token: 'info',
    generic: 'default',
  }
  return colors[type] || 'default'
}

const columns = computed(() => [
  { title: '名称', key: 'name', ellipsis: true, width: 140 },
  {
    title: '类型', key: 'type', width: 90,
    render: (r: any) => h(NTag, { type: typeColor(r.type), size: 'small' }, () => getTypeLabel(r.type)),
  },
  { title: '环境变量', key: 'key', width: 110, render: (r: any) => h(NText, { code: true }, () => `$${r.key}`) },
  {
    title: '有效期', key: 'expires_at', width: 130,
    render: (r: any) => {
      if (!r.expires_at) return h(NText, { depth: 3 }, () => '—')
      const d = daysLeft(r.expires_at)
      const children: any[] = [h('span', null, r.expires_at?.slice(0, 10))]
      if (d !== null && d <= 7 && d > 0) {
        children.push(h(NIcon, { size: 14, color: '#f0a020', style: 'margin-left:6px;vertical-align:middle' }, () => h(AlertCircleOutline)))
        children.push(h(NText, { type: 'warning', style: 'margin-left:2px' }, () => `${d}d`))
      }
      if (d !== null && d <= 0) {
        children.push(h(NText, { type: 'error', style: 'margin-left:6px' }, () => '已过期'))
      }
      return h('div', { style: 'display:flex;align-items:center' }, children)
    },
  },
  { title: '描述', key: 'description', ellipsis: true, width: 120 },
  { title: '更新时间', key: 'updated_at', width: 160 },
  {
    title: '操作', key: 'actions', width: 160,
    render: (r: any) => h(NSpace, null, () => [
      h(NButton, { size: 'small', onClick: () => handleReveal(r.id) }, () => '查看'),
      h(NButton, { size: 'small', type: 'error', onClick: () => { deleting.value = r; showDelete.value = true } }, () => '删除'),
    ]),
  },
])

async function load() {
  loading.value = true
  try {
    const res = await fetchCredentials()
    credentials.value = res.data
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const payload: any = { ...createForm.value }
    if (!payload.expires_at) payload.expires_at = null
    await createCredential(payload)
    message.success('创建成功')
    showCreate.value = false
    createForm.value = { name: '', key: '', value: '', description: '', type: 'generic', expires_at: null }
    load()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function handleReveal(id: number) {
  try {
    const res = await revealCredential(id)
    revealed.value = res.data
    showReveal.value = true
  } catch (e: any) {
    message.error(e.message)
  }
}

async function confirmDelete() {
  if (!deleting.value) return
  deleting_loading.value = true
  try {
    await deleteCredential(deleting.value.id)
    message.success('删除成功')
    showDelete.value = false
    load()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    deleting_loading.value = false
  }
}

onMounted(load)
</script>
