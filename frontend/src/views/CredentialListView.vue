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

    <n-modal v-model:show="showCreate" title="新建密钥" @positive-click="handleCreate" positive-text="保存">
      <n-form ref="createFormRef" :model="createForm" :rules="createRules" label-placement="top">
        <n-form-item path="name" label="名称">
          <n-input v-model:value="createForm.name" placeholder="如: K8s 集群 Token" />
        </n-form-item>
        <n-form-item path="key" label="环境变量名">
          <n-input v-model:value="createForm.key" placeholder="如: K8S_TOKEN" />
        </n-form-item>
        <n-form-item path="value" label="密钥值">
          <n-input type="textarea" v-model:value="createForm.value" placeholder="密钥内容" />
        </n-form-item>
        <n-form-item path="description" label="描述">
          <n-input v-model:value="createForm.description" placeholder="用途说明" />
        </n-form-item>
      </n-form>
    </n-modal>

    <n-modal v-model:show="showReveal" title="查看密钥">
      <n-descriptions v-if="revealed" :columns="1" label-placement="left">
        <n-descriptions-item label="名称">{{ revealed.name }}</n-descriptions-item>
        <n-descriptions-item label="环境变量">${{ revealed.key }}</n-descriptions-item>
        <n-descriptions-item label="值">
          <n-text code>{{ revealed.value }}</n-text>
        </n-descriptions-item>
      </n-descriptions>
    </n-modal>

    <n-modal v-model:show="showDelete" title="确认删除" @positive-click="confirmDelete" positive-text="删除"
      type="warning">
      <p>确定要删除密钥 "{{ deleting?.name }}" 吗？</p>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import {
  NH3, NSpace, NButton, NIcon, NDataTable, NModal, NForm, NFormItem,
  NInput, NDescriptions, NDescriptionsItem, NText, useMessage,
} from 'naive-ui'
import { AddOutline } from '@vicons/ionicons5'
import {
  fetchCredentials, createCredential, revealCredential, deleteCredential,
  type Credential, type CredentialReveal,
} from '@/api/credentials'

const message = useMessage()

const credentials = ref<Credential[]>([])
const loading = ref(false)
const showCreate = ref(false)
const showReveal = ref(false)
const showDelete = ref(false)
const deleting = ref<Credential | null>(null)
const revealed = ref<CredentialReveal | null>(null)

const createForm = ref({ name: '', key: '', value: '', description: '' })
const createFormRef = ref()
const createRules = {
  name: [{ required: true, message: '请输入名称' }],
  key: [{ required: true, message: '请输入环境变量名' }],
  value: [{ required: true, message: '请输入密钥值' }],
}

const columns: any[] = [
  { title: '名称', key: 'name', ellipsis: true },
  { title: '环境变量', key: 'key', render: (r: any) => h('n-text', { code: true }, `$${r.key}`) },
  { title: '描述', key: 'description', ellipsis: true },
  { title: '更新时间', key: 'updated_at', width: 170 },
  {
    title: '操作', key: 'actions', width: 160,
    render: (r: any) => h(NSpace, null, () => [
      h(NButton, { size: 'small', onClick: () => handleReveal(r.id) }, () => '查看'),
      h(NButton, { size: 'small', type: 'error', onClick: () => { deleting.value = r; showDelete.value = true } }, () => '删除'),
    ]),
  },
]

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
  if (!valid) return false
  try {
    await createCredential(createForm.value)
    message.success('创建成功')
    showCreate.value = false
    createForm.value = { name: '', key: '', value: '', description: '' }
    load()
    return true
  } catch (e: any) {
    message.error(e.message)
    return false
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
  try {
    await deleteCredential(deleting.value.id)
    message.success('删除成功')
    load()
  } catch (e: any) {
    message.error(e.message)
  }
}

onMounted(load)
</script>
