<template>
  <div>
    <n-space justify="space-between" style="margin-bottom: 16px">
      <n-h3 style="margin: 0">主机运维</n-h3>
      <n-button type="primary" @click="showCreate = true">
        <template #icon><n-icon><AddOutline /></n-icon></template>
        新建主机
      </n-button>
    </n-space>

    <n-data-table :columns="columns" :data="hosts" :loading="loading" :row-key="(r: any) => r.id" />

    <!-- Create Modal -->
    <n-modal v-model:show="showCreate" preset="card" title="新建主机" style="width: 520px">
      <n-space style="margin-bottom: 12px">
        <n-button dashed @click="openEc2Import">
          <template #icon><n-icon><CloudOutline /></n-icon></template>
          从 EC2 导入
        </n-button>
        <n-text v-if="createForm.aws_instance_id" depth="3" style="font-size:12px">
          已导入: {{ createForm.aws_instance_id }}
        </n-text>
      </n-space>
      <n-form ref="createFormRef" :model="createForm" :rules="formRules" label-placement="top">
        <n-form-item path="name" label="名称">
          <n-input v-model:value="createForm.name" placeholder="如: 生产服务器" />
        </n-form-item>
        <n-grid :cols="2" :x-gap="16">
          <n-grid-item>
            <n-form-item path="hostname" label="主机地址">
              <n-input v-model:value="createForm.hostname" placeholder="IP 或域名" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item path="port" label="SSH 端口">
              <n-input-number v-model:value="createForm.port" :min="1" :max="65535" style="width: 100%" />
            </n-form-item>
          </n-grid-item>
        </n-grid>
        <n-form-item path="username" label="用户名">
          <n-input v-model:value="createForm.username" placeholder="如: root" />
        </n-form-item>
        <n-form-item path="credential_id" label="认证凭证（选填）">
          <n-select
            v-model:value="createForm.credential_id"
            :options="sshCredentialOptions"
            placeholder="选择 SSH 密钥或密码凭证"
            clearable
            filterable
          />
        </n-form-item>
        <n-form-item path="description" label="描述">
          <n-input v-model:value="createForm.description" placeholder="可选描述" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showCreate = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleCreate">确认</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Edit Modal -->
    <n-modal v-model:show="showEdit" preset="card" title="编辑主机" style="width: 520px">
      <n-form ref="editFormRef" :model="editForm" :rules="formRules" label-placement="top">
        <n-form-item path="name" label="名称">
          <n-input v-model:value="editForm.name" placeholder="如: 生产服务器" />
        </n-form-item>
        <n-grid :cols="2" :x-gap="16">
          <n-grid-item>
            <n-form-item path="hostname" label="主机地址">
              <n-input v-model:value="editForm.hostname" placeholder="IP 或域名" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item path="port" label="SSH 端口">
              <n-input-number v-model:value="editForm.port" :min="1" :max="65535" style="width: 100%" />
            </n-form-item>
          </n-grid-item>
        </n-grid>
        <n-form-item path="username" label="用户名">
          <n-input v-model:value="editForm.username" placeholder="如: root" />
        </n-form-item>
        <n-form-item path="credential_id" label="认证凭证（选填）">
          <n-select
            v-model:value="editForm.credential_id"
            :options="sshCredentialOptions"
            placeholder="选择 SSH 密钥或密码凭证"
            clearable
            filterable
          />
        </n-form-item>
        <n-form-item path="description" label="描述">
          <n-input v-model:value="editForm.description" placeholder="可选描述" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showEdit = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleUpdate">保存</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- EC2 Import Modal -->
    <n-modal v-model:show="showEc2Import" preset="card" title="从 EC2 导入主机" style="width: 680px">
      <n-space vertical :size="12">
        <n-grid :cols="3" :x-gap="12">
          <n-grid-item>
            <n-select v-model:value="ec2AwsCredentialId" :options="awsCredentialOptions" placeholder="AWS 凭证" />
          </n-grid-item>
          <n-grid-item>
            <n-select v-model:value="ec2Region" :options="ec2RegionOptions" placeholder="区域" />
          </n-grid-item>
          <n-grid-item>
            <n-select v-model:value="osType" :options="osTypeOptions" placeholder="操作系统" />
          </n-grid-item>
        </n-grid>
        <n-button type="primary" :loading="ec2Loading" block @click="loadEc2Instances">
          查询实例
        </n-button>
        <n-data-table
          :columns="ec2Columns"
          :data="ec2Instances"
          :loading="ec2Loading"
          :row-key="(r: any) => r.instance_id"
          size="small"
          :max-height="300"
          virtual-scroll
        />
      </n-space>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { h, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, NTag, NButton, NIcon, NSpace, NDataTable, NModal, NForm, NFormItem, NInput, NInputNumber, NSelect, NH3, NGrid, NGridItem, NText, NProgress, useDialog } from 'naive-ui'
import { AddOutline, PlayOutline, CloudOutline } from '@vicons/ionicons5'
import { fetchHosts, createHost, updateHost, deleteHost, importFromEc2, regenerateAgentToken } from '@/api/hosts'
import { fetchCredentials, getTypeLabel } from '@/api/credentials'
import { fetchInstances, fetchRegions, type Ec2Instance } from '@/api/aws'
import type { Host, HostCreate, HostUpdate } from '@/api/hosts'
import type { Credential } from '@/api/credentials'
import type { DataTableColumn } from 'naive-ui'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()

const hosts = ref<Host[]>([])
const credentials = ref<Credential[]>([])
const loading = ref(false)
const saving = ref(false)

const showCreate = ref(false)
const showEdit = ref(false)
const showEc2Import = ref(false)
const editingId = ref<number | null>(null)

const createForm = ref<HostCreate>({
  name: '', hostname: '', port: 22, username: 'root',
  credential_id: null, aws_instance_id: null, aws_region: null, aws_credential_id: null,
  description: '',
})
const editForm = ref<HostCreate>({
  name: '', hostname: '', port: 22, username: 'root',
  credential_id: null, aws_instance_id: null, aws_region: null, aws_credential_id: null,
  description: '',
})
const createFormRef = ref()
const editFormRef = ref()

const formRules = {
  name: [{ required: true, message: '请输入名称' }],
  hostname: [{ required: true, message: '请输入主机地址' }],
  username: [{ required: true, message: '请输入用户名' }],
}

// EC2 import state
const ec2Instances = ref<Ec2Instance[]>([])
const ec2AwsCredentialId = ref<number | null>(null)
const ec2Region = ref<string | null>(null)
const ec2Loading = ref(false)
const osType = ref('amazon-linux')
const osTypeOptions = [
  { label: 'Amazon Linux → ec2-user', value: 'amazon-linux' },
  { label: 'Ubuntu → ubuntu', value: 'ubuntu' },
  { label: 'Debian → admin', value: 'debian' },
  { label: 'CentOS / RHEL → root', value: 'centos-rhel' },
  { label: 'SUSE → ec2-user', value: 'suse' },
]

const OS_USER_MAP: Record<string, string> = {
  'amazon-linux': 'ec2-user',
  'ubuntu': 'ubuntu',
  'debian': 'admin',
  'centos-rhel': 'root',
  'suse': 'ec2-user',
}

// Credential options filtered for SSH types only
const sshCredentialOptions = computed(() =>
  credentials.value
    .filter(c => ['ssh_key', 'ssh_password', 'generic'].includes(c.type))
    .map(c => ({ label: `${c.name} (${getTypeLabel(c.type)})`, value: c.id }))
)

// AWS credential options (type=aws only)
const awsCredentialOptions = computed(() =>
  credentials.value
    .filter(c => c.type === 'aws')
    .map(c => ({ label: c.name, value: c.id }))
)

// Region options
const ec2RegionOptions = ref<{ label: string; value: string }[]>([])

// EC2 table columns
const ec2Columns: DataTableColumn<Ec2Instance>[] = [
  { title: '名称', key: 'name', width: 140, ellipsis: { tooltip: true } },
  { title: '实例 ID', key: 'instance_id', width: 140 },
  { title: '类型', key: 'instance_type', width: 90 },
  {
    title: '状态', key: 'state', width: 70,
    render: (r) => h(NTag, { type: r.state === 'running' ? 'success' : 'error', size: 'small' }, () => r.state),
  },
  { title: 'IP', key: 'public_ip', width: 120, render: (r) => r.public_ip || r.private_ip },
  {
    title: '', key: 'pick', width: 60,
    render: (r) => r.state === 'running'
      ? h(NButton, { size: 'tiny', type: 'primary', onClick: () => fillFromEc2(r) }, () => '选择')
      : h(NText, { depth: 3 }, () => '—'),
  },
]

// Table columns
function getCredentialLabel(credId: number | null) {
  if (credId === null) return '-'
  const cred = credentials.value.find(c => c.id === credId)
  return cred ? `${cred.name}` : '-'
}

const columns: DataTableColumn<Host>[] = [
  { title: '名称', key: 'name', width: 140 },
  { title: '主机地址', key: 'hostname', width: 170, render: (r) => `${r.hostname}:${r.port}` },
  { title: '用户名', key: 'username', width: 80 },
  {
    title: '在线', key: 'is_online', width: 60,
    render: (r) => h(NTag, { type: r.is_online ? 'success' : 'default', size: 'small', round: true },
      () => r.is_online ? '在线' : '离线'),
  },
  {
    title: 'CPU', key: 'cpu_usage', width: 100,
    render: (r) => {
      const pct = r.cpu_usage || 0
      const color = pct >= 90 ? '#d03050' : pct >= 70 ? '#f0a020' : '#18a058'
      return h('div', { style: 'display:flex;align-items:center;gap:6px' }, [
        h(NProgress, { percentage: pct, color, height: 6, style: 'flex:1;min-width:50px',
          showIndicator: false, borderRaius: 3 }),
        h('span', { style: 'font-size:12px;white-space:nowrap' }, `${pct}%`),
      ])
    },
  },
  {
    title: '内存', key: 'mem_usage', width: 100,
    render: (r) => {
      const pct = r.mem_usage || 0
      const color = pct >= 90 ? '#d03050' : pct >= 70 ? '#f0a020' : '#18a058'
      return h('div', { style: 'display:flex;align-items:center;gap:6px' }, [
        h(NProgress, { percentage: pct, color, height: 6, style: 'flex:1;min-width:50px',
          showIndicator: false, borderRaius: 3 }),
        h('span', { style: 'font-size:12px;white-space:nowrap' }, `${pct}%`),
      ])
    },
  },
  {
    title: '最后上报', key: 'last_seen_at', width: 90,
    render: (r) => h('span', { style: 'font-size:12px' }, relativeTime(r.last_seen_at)),
  },
  { title: '凭证', key: 'credential_id', width: 110, render: (r) => getCredentialLabel(r.credential_id) },
  { title: '描述', key: 'description', width: 130, ellipsis: { tooltip: true }, render: (r) => r.description || '-' },
  { title: '更新时间', key: 'updated_at', width: 150, render: (r) => formatTime(r.updated_at) },
  {
    title: '操作', key: 'actions', width: 200,
    render: (row) => h(NSpace, { size: 'small' }, {
      default: () => [
        h(NButton, { size: 'small', type: 'primary', ghost: true, onClick: () => handleConnect(row) },
          { icon: () => h(NIcon, null, () => h(PlayOutline)), default: () => '连接' }),
        h(NButton, { size: 'small', quaternary: true, onClick: () => handleEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', quaternary: true, onClick: () => handleRegenToken(row) }, { default: () => 'Token' }),
        h(NButton, { size: 'small', quaternary: true, type: 'error', onClick: () => handleDelete(row) }, { default: () => '删除' }),
      ],
    }),
  },
]

function relativeTime(val: string | null): string {
  if (!val) return '-'
  const diff = Date.now() - new Date(val).getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return '刚刚'
  if (sec < 3600) return `${Math.floor(sec / 60)}分钟前`
  if (sec < 86400) return `${Math.floor(sec / 3600)}小时前`
  return `${Math.floor(sec / 86400)}天前`
}

async function handleRegenToken(row: Host) {
  dialog.warning({
    title: '重新生成 Agent Token',
    content: `确定要重新生成 "${row.name}" 的 Agent Token 吗？旧的 Token 将立即失效。`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const resp = await regenerateAgentToken(row.id)
        const token = resp.data.agent_token
        dialog.success({
          title: '新 Token',
          content: `主机 "${row.name}" 的新 Token:\n\n${token}\n\n请复制保存，关闭后无法再次查看。`,
          positiveText: '复制',
          onPositiveClick: () => {
            navigator.clipboard.writeText(token).catch(() => {})
          },
        })
      } catch (e: any) {
        message.error(e.message || '生成失败')
      }
    },
  })
}

function formatTime(val: string | null) {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

// -- Lifecycle & loaders ---------------------------------------------------

onMounted(() => {
  loadHosts()
  loadCredentials()
  loadAwsRegions()
})

async function loadHosts() {
  loading.value = true
  try {
    const resp = await fetchHosts()
    hosts.value = resp.data
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadCredentials() {
  try {
    const resp = await fetchCredentials()
    credentials.value = resp.data
  } catch (_e) { /* non-critical */ }
}

async function loadAwsRegions() {
  try {
    const resp = await fetchRegions()
    ec2RegionOptions.value = (resp.data.regions || []).map((r: string) => ({ label: r, value: r }))
    if (ec2RegionOptions.value.length > 0 && !ec2Region.value) {
      ec2Region.value = ec2RegionOptions.value[0].value
    }
  } catch (_e) { /* ignore */ }
}

// -- EC2 import ------------------------------------------------------------

function openEc2Import() {
  if (awsCredentialOptions.value.length > 0 && !ec2AwsCredentialId.value) {
    ec2AwsCredentialId.value = awsCredentialOptions.value[0].value
  }
  showEc2Import.value = true
}

async function loadEc2Instances() {
  if (!ec2AwsCredentialId.value || !ec2Region.value) {
    message.warning('请选择 AWS 凭证和区域')
    return
  }
  ec2Loading.value = true
  try {
    const resp = await fetchInstances(ec2AwsCredentialId.value, ec2Region.value)
    ec2Instances.value = resp.data || []
  } catch (e: any) {
    message.error(e.message || '加载实例失败')
  } finally {
    ec2Loading.value = false
  }
}

function fillFromEc2(inst: Ec2Instance) {
  createForm.value.name = inst.name
  createForm.value.hostname = inst.public_ip || inst.private_ip
  createForm.value.username = OS_USER_MAP[osType.value] || 'root'
  createForm.value.port = 22
  createForm.value.description = `EC2: ${inst.instance_id} (${inst.instance_type}, ${inst.availability_zone})`
  createForm.value.aws_instance_id = inst.instance_id
  createForm.value.aws_region = ec2Region.value
  createForm.value.aws_credential_id = ec2AwsCredentialId.value
  showEc2Import.value = false
  message.success(`已填充: ${inst.name}`)
}

// -- CRUD ------------------------------------------------------------------

async function handleCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (createForm.value.aws_instance_id) {
      await importFromEc2({
        aws_credential_id: createForm.value.aws_credential_id!,
        aws_region: createForm.value.aws_region!,
        aws_instance_id: createForm.value.aws_instance_id,
        name: createForm.value.name,
        username: createForm.value.username,
        port: createForm.value.port,
        credential_id: createForm.value.credential_id,
        description: createForm.value.description,
      })
    } else {
      await createHost(createForm.value)
    }
    message.success('创建成功')
    showCreate.value = false
    createForm.value = {
      name: '', hostname: '', port: 22, username: 'root',
      credential_id: null, aws_instance_id: null, aws_region: null, aws_credential_id: null,
      description: '',
    }
    await loadHosts()
  } catch (e: any) {
    message.error(e.message || '创建失败')
  } finally {
    saving.value = false
  }
}

function handleEdit(row: Host) {
  editingId.value = row.id
  editForm.value = {
    name: row.name, hostname: row.hostname, port: row.port,
    username: row.username, credential_id: row.credential_id,
    aws_instance_id: row.aws_instance_id, aws_region: row.aws_region,
    aws_credential_id: row.aws_credential_id, description: row.description,
  }
  showEdit.value = true
}

async function handleUpdate() {
  if (editingId.value === null) return
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await updateHost(editingId.value, editForm.value)
    message.success('更新成功')
    showEdit.value = false
    editingId.value = null
    await loadHosts()
  } catch (e: any) {
    message.error(e.message || '更新失败')
  } finally {
    saving.value = false
  }
}

function handleDelete(row: Host) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除主机 "${row.name}" 吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteHost(row.id)
        message.success('删除成功')
        await loadHosts()
      } catch (e: any) {
        message.error(e.message || '删除失败')
      }
    },
  })
}

function handleConnect(row: Host) {
  router.push(`/hosts/${row.id}/terminal`)
}
</script>
