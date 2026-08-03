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
        <n-form-item v-if="createForm.type !== 'aws'" path="value" label="密钥值">
          <n-input type="textarea" v-model:value="createForm.value" placeholder="密钥内容" :rows="4" />
        </n-form-item>

        <!-- AWS 专用字段 -->
        <template v-if="createForm.type === 'aws'">
          <n-form-item path="aws_access_key_id" label="Access Key ID">
            <n-input v-model:value="awsForm.access_key_id" placeholder="AKIA..." />
          </n-form-item>
          <n-form-item path="aws_secret_access_key" label="Secret Access Key">
            <n-input v-model:value="awsForm.secret_access_key" type="password" show-password-on="click" placeholder="密钥内容" />
          </n-form-item>
          <n-form-item path="aws_region" label="Region">
            <n-select v-model:value="awsForm.region" :options="awsRegionOptions" placeholder="ap-southeast-1" filterable clearable />
          </n-form-item>
          <n-form-item path="aws_session_token" label="Session Token (可选)">
            <n-input v-model:value="awsForm.session_token" type="textarea" placeholder="临时会话令牌（选填）" :rows="2" />
          </n-form-item>
          <n-form-item>
            <n-button :loading="validatingAws" @click="handleValidateAws">验证凭证</n-button>
          </n-form-item>
        </template>

        <n-form-item path="expires_at" label="截止有效期">
          <n-space style="width: 100%">
            <n-date-picker v-model:formatted-value="createForm.expires_at" type="datetime"
              value-format="yyyy-MM-dd'T'HH:mm:ss" style="flex: 1" placeholder="选填，过期后可用于告警" />
            <n-button v-if="createForm.type === 'kubeconfig'" size="small" :loading="parsingKc" @click="handleParseKubeconfig">
              自动解析
            </n-button>
          </n-space>
        </n-form-item>
        <n-form-item path="alert_enabled" label="到期告警通知">
          <n-space align="center">
            <n-switch v-model:value="createForm.alert_enabled" />
            <n-text depth="3" style="font-size:12px">
              {{ createForm.alert_enabled ? '到期前 7 天发送通知' : '不通知' }}
            </n-text>
          </n-space>
        </n-form-item>
        <n-form-item v-if="createForm.alert_enabled" path="notification_group_id" label="通知组">
          <n-select v-model:value="createForm.notification_group_id" :options="groupOptions" placeholder="选择通知组（选填）" clearable style="width: 100%" />
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
          {{ formatExpiry(revealed.expires_at) }}
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
import axios from 'axios'
import {
  NH3, NSpace, NButton, NIcon, NDataTable, NModal, NForm, NFormItem,
  NInput, NSelect, NDatePicker, NGrid, NGridItem, NSwitch,
  NDescriptions, NDescriptionsItem, NText, NTag, useMessage,
} from 'naive-ui'
import { AddOutline, AlertCircleOutline } from '@vicons/ionicons5'
import {
  fetchCredentials, createCredential, revealCredential, deleteCredential, toggleCredentialAlert,
  type Credential, type CredentialReveal, CREDENTIAL_TYPES, getTypeLabel,
} from '@/api/credentials'
import { fetchGroups } from '@/api/notification-groups'
import type { NotificationGroup } from '@/api/notification-groups'

const message = useMessage()

const credentials = ref<Credential[]>([])
const loading = ref(false)
const showCreate = ref(false)
const showReveal = ref(false)
const showDelete = ref(false)
const saving = ref(false)
const parsingKc = ref(false)
const validatingAws = ref(false)
const deleting_loading = ref(false)
const awsForm = ref({
  access_key_id: '',
  secret_access_key: '',
  region: 'ap-southeast-1',
  session_token: '',
})
const awsRegionOptions = [
  { label: 'ap-southeast-1 (新加坡)', value: 'ap-southeast-1' },
  { label: 'us-east-1 (弗吉尼亚)', value: 'us-east-1' },
  { label: 'eu-west-1 (爱尔兰)', value: 'eu-west-1' },
  { label: 'ap-northeast-1 (东京)', value: 'ap-northeast-1' },
  { label: 'ap-southeast-2 (悉尼)', value: 'ap-southeast-2' },
  { label: 'us-west-2 (俄勒冈)', value: 'us-west-2' },
]
const deleting = ref<Credential | null>(null)
const revealed = ref<CredentialReveal | null>(null)
const groups = ref<NotificationGroup[]>([])

const typeOptions = CREDENTIAL_TYPES.map(t => ({ label: t.label, value: t.value }))
const groupOptions = computed(() =>
  groups.value.map((g) => ({ label: g.name, value: g.id }))
)

const createForm = ref({
  name: '', key: '', value: '', description: '',
  type: 'generic', expires_at: null as string | null,
  alert_enabled: true,
  notification_group_id: null as number | null,
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

function formatExpiry(isoStr: string | null): string {
  if (!isoStr) return '—'
  return isoStr.replace('T', ' ').slice(0, 16)
}

type TagColor = 'warning' | 'error' | 'info' | 'default'
function typeColor(type: string): TagColor {
  const colors: Record<string, TagColor> = {
    kubeconfig: 'warning',
    tls_cert: 'error',
    api_token: 'info',
    aws: 'info',
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
    title: '有效期', key: 'expires_at', width: 160,
    render: (r: any) => {
      if (!r.expires_at) return h(NText, { depth: 3 }, () => '—')
      const d = daysLeft(r.expires_at)
      const children: any[] = [h('span', null, formatExpiry(r.expires_at))]
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
  {
    title: '告警', key: 'alert_enabled', width: 70,
    render: (r: any) => {
      if (!r.expires_at) return h(NText, { depth: 3 }, () => '—')
      return h(NSwitch, {
        size: 'small',
        value: r.alert_enabled,
        'onUpdate:value': (val: boolean) => handleToggleAlert(r, val),
      })
    },
  },
  { title: '更新时间', key: 'updated_at', width: 160 },
  {
    title: '操作', key: 'actions', width: 160,
    render: (r: any) => h(NSpace, null, () => [
      h(NButton, { size: 'small', onClick: () => handleReveal(r.id) }, () => '查看'),
      h(NButton, { size: 'small', type: 'error', onClick: () => { deleting.value = r; showDelete.value = true } }, () => '删除'),
    ]),
  },
])

async function handleToggleAlert(cred: Credential, enabled: boolean) {
  try {
    await toggleCredentialAlert(cred.id, enabled)
    cred.alert_enabled = enabled
    message.success(enabled ? '已开启告警通知' : '已关闭告警通知')
  } catch (e: any) {
    message.error(e.message || '操作失败')
    load()
  }
}

async function handleParseKubeconfig() {
  if (!createForm.value.value.trim()) {
    message.warning('请先填入 kubeconfig 内容')
    return
  }
  parsingKc.value = true
  try {
    const resp = await axios.post('/api/v1/credentials/parse-kubeconfig', {
      value: createForm.value.value,
    })
    createForm.value.expires_at = resp.data.expires_at
    message.success(`已解析有效期: ${formatExpiry(resp.data.expires_at)} (剩余 ${resp.data.days_left} 天)`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || '解析失败')
  } finally {
    parsingKc.value = false
  }
}

async function handleValidateAws() {
  if (!awsForm.value.access_key_id.trim() || !awsForm.value.secret_access_key.trim()) {
    message.warning('请先填入 Access Key ID 和 Secret Access Key')
    return
  }
  validatingAws.value = true
  try {
    const valueJson = JSON.stringify({
      access_key_id: awsForm.value.access_key_id.trim(),
      secret_access_key: awsForm.value.secret_access_key.trim(),
      region: awsForm.value.region || 'ap-southeast-1',
      session_token: awsForm.value.session_token.trim() || undefined,
    })
    const resp = await axios.post('/api/v1/aws/credentials/validate', { value: valueJson })
    message.success(`验证成功: 账号 ${resp.data.account_id}`)
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.message || '验证失败')
  } finally {
    validatingAws.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const res = await fetchCredentials()
    credentials.value = res.data
  } finally {
    loading.value = false
  }
}

async function loadGroups() {
  try {
    const resp = await fetchGroups()
    groups.value = resp.data
  } catch { /* ignore */ }
}

async function handleCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const payload: any = { ...createForm.value }
    if (!payload.expires_at) payload.expires_at = null
    if (createForm.value.type === 'aws') {
      payload.key = awsForm.value.access_key_id.trim().slice(0, 20) // prefix as env hint
      payload.value = JSON.stringify({
        access_key_id: awsForm.value.access_key_id.trim(),
        secret_access_key: awsForm.value.secret_access_key.trim(),
        region: awsForm.value.region || 'ap-southeast-1',
        session_token: awsForm.value.session_token.trim() || undefined,
      })
    }
    await createCredential(payload)
    message.success('创建成功')
    showCreate.value = false
    createForm.value = { name: '', key: '', value: '', description: '', type: 'generic', expires_at: null, alert_enabled: true, notification_group_id: null }
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

onMounted(() => {
  load()
  loadGroups()
})
</script>
