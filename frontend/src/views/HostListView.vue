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

    <n-modal v-model:show="showCreate" preset="card" title="新建主机" style="width: 520px">
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
            :options="credentialOptions"
            placeholder="选择密钥或 SSH 凭证"
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
            :options="credentialOptions"
            placeholder="选择密钥或 SSH 凭证"
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
  </div>
</template>

<script setup lang="ts">
import { h, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, NTag, NButton, NIcon, NSpace, NDataTable, NModal, NForm, NFormItem, NInput, NInputNumber, NSelect, NH3, NGrid, NGridItem, useDialog } from 'naive-ui'
import { AddOutline, PlayOutline } from '@vicons/ionicons5'
import { fetchHosts, createHost, updateHost, deleteHost } from '@/api/hosts'
import { fetchCredentials, getTypeLabel } from '@/api/credentials'
import type { Host, HostCreate } from '@/api/hosts'
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
const editingId = ref<number | null>(null)

const createForm = ref<HostCreate>({ name: '', hostname: '', port: 22, username: 'root', credential_id: null, description: '' })
const editForm = ref<HostCreate>({ name: '', hostname: '', port: 22, username: 'root', credential_id: null, description: '' })
const createFormRef = ref()
const editFormRef = ref()

const formRules = {
  name: [{ required: true, message: '请输入名称' }],
  hostname: [{ required: true, message: '请输入主机地址' }],
  username: [{ required: true, message: '请输入用户名' }],
}

const credentialOptions = ref<{ label: string; value: number }[]>([])

async function loadCredentials() {
  try {
    const resp = await fetchCredentials()
    credentials.value = resp.data
    credentialOptions.value = resp.data.map((c: Credential) => ({
      label: `${c.name} (${getTypeLabel(c.type)})`,
      value: c.id,
    }))
  } catch (_e) { /* non-critical */ }
}

function getCredentialLabel(credId: number | null) {
  if (credId === null) return '-'
  const cred = credentials.value.find(c => c.id === credId)
  return cred ? `${cred.name}` : '-'
}

const columns: DataTableColumn<Host>[] = [
  { title: '名称', key: 'name', width: 160 },
  { title: '主机地址', key: 'hostname', width: 180, render: (r) => `${r.hostname}:${r.port}` },
  { title: '用户名', key: 'username', width: 90 },
  { title: '凭证', key: 'credential_id', width: 130, render: (r) => getCredentialLabel(r.credential_id) },
  { title: '描述', key: 'description', width: 160, ellipsis: { tooltip: true }, render: (r) => r.description || '-' },
  { title: '更新时间', key: 'updated_at', width: 170, render: (r) => formatTime(r.updated_at) },
  {
    title: '操作', key: 'actions', width: 160,
    render: (row) => h(NSpace, { size: 'small' }, {
      default: () => [
        h(NButton, { size: 'small', type: 'primary', ghost: true, onClick: () => handleConnect(row) },
          { icon: () => h(NIcon, null, () => h(PlayOutline)), default: () => '连接' }),
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

async function loadHosts() {
  loading.value = true
  try {
    const resp = await fetchHosts()
    hosts.value = resp.data
  } catch (e: any) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await createHost(createForm.value)
    message.success('创建成功')
    showCreate.value = false
    createForm.value = { name: '', hostname: '', port: 22, username: 'root', credential_id: null, description: '' }
    await loadHosts()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '创建失败')
  } finally {
    saving.value = false
  }
}

function handleEdit(row: Host) {
  editingId.value = row.id
  editForm.value = { name: row.name, hostname: row.hostname, port: row.port, username: row.username, credential_id: row.credential_id, description: row.description }
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
    message.error(e.response?.data?.detail || '更新失败')
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
        message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

function handleConnect(row: Host) {
  router.push(`/hosts/${row.id}/terminal`)
}

onMounted(() => {
  loadHosts()
  loadCredentials()
})
</script>
