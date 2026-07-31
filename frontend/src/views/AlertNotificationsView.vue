<template>
  <div>
    <n-h3 style="margin: 0 0 16px">告警通知</n-h3>

    <n-tabs v-model:value="activeTab" type="line">
      <n-tab-pane name="groups" tab="通知组">
        <n-space style="margin-bottom: 12px">
          <n-button type="primary" size="small" @click="openGroupCreate">
            <template #icon><n-icon><AddOutline /></n-icon></template>
            新建通知组
          </n-button>
        </n-space>
        <n-data-table :columns="groupColumns" :data="groups" :loading="loading" :row-key="(r: any) => r.id" size="small" />
      </n-tab-pane>

      <n-tab-pane name="recipients" tab="通知对象">
        <n-space style="margin-bottom: 12px">
          <n-button type="primary" size="small" @click="openRecipientCreate">
            <template #icon><n-icon><AddOutline /></n-icon></template>
            新建通知对象
          </n-button>
        </n-space>
        <n-data-table :columns="recipientColumns" :data="recipients" :loading="loading" :row-key="(r: any) => r.id" size="small" />
      </n-tab-pane>
    </n-tabs>

    <!-- Group Modal -->
    <n-modal v-model:show="showGroupForm" preset="card" :title="editingGroupId ? '编辑通知组' : '新建通知组'" style="width: 480px">
      <n-form :model="groupForm" label-placement="top">
        <n-form-item label="名称" required>
          <n-input v-model:value="groupForm.name" placeholder="如: 运维团队" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showGroupForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleGroupSave">确认</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Recipient Modal -->
    <n-modal v-model:show="showRecipientForm" preset="card" :title="editingRecipientId ? '编辑通知对象' : '新建通知对象'" style="width: 480px">
      <n-form :model="recipientForm" label-placement="top">
        <n-form-item label="名称" required>
          <n-input v-model:value="recipientForm.name" placeholder="如: 张三" />
        </n-form-item>
        <n-form-item label="渠道类型">
          <n-select v-model:value="recipientForm.channel_type" :options="channelOptions" />
        </n-form-item>
        <n-form-item label="地址" required>
          <n-input v-model:value="recipientForm.address" :placeholder="recipientForm.channel_type === 'dingtalk' ? '被@人员手机号，如: 13800138000' : '如: zhangsan@example.com'" />
        </n-form-item>
        <n-form-item label="所属通知组" required>
          <n-select v-model:value="recipientForm.group_id" :options="groupSelectOptions" placeholder="选择通知组" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showRecipientForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleRecipientSave">确认</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { h, ref, computed, onMounted } from 'vue'
import { useMessage, useDialog, NTag, NButton, NIcon, NSpace, NDataTable, NModal, NForm, NFormItem, NInput, NSelect, NH3, NTabs, NTabPane } from 'naive-ui'
import { AddOutline } from '@vicons/ionicons5'
import {
  fetchGroups, createGroup, updateGroup, deleteGroup,
  fetchRecipients, createRecipient, updateRecipient, deleteRecipient,
} from '@/api/notification-groups'
import type { NotificationGroup, NotificationRecipient } from '@/api/notification-groups'

const message = useMessage()
const dialog = useDialog()

const activeTab = ref('groups')
const loading = ref(false)
const saving = ref(false)

// ── Groups ───────────────────────────────────────────────────────────────────

const groups = ref<NotificationGroup[]>([])
const showGroupForm = ref(false)
const editingGroupId = ref<number | null>(null)
const groupForm = ref({ name: '' })

const groupColumns = [
  { title: '名称', key: 'name', ellipsis: true },
  { title: '成员数', key: 'recipients', width: 80, render: (r: NotificationGroup) => String(r.recipients?.length || 0) },
  {
    title: '成员', key: 'members', width: 200, ellipsis: { tooltip: true },
    render: (r: NotificationGroup) => (r.recipients || []).map((rc) => rc.name).join(', ') || '-',
  },
  {
    title: '操作', key: 'actions', width: 120,
    render: (row: NotificationGroup) => h(NSpace, { size: 'small' }, () => [
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => openGroupEdit(row) }, () => '编辑'),
      h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => handleGroupDelete(row) }, () => '删除'),
    ]),
  },
]

const groupSelectOptions = computed(() =>
  groups.value.map((g) => ({ label: g.name, value: g.id }))
)

// ── Recipients ───────────────────────────────────────────────────────────────

const recipients = ref<NotificationRecipient[]>([])
const showRecipientForm = ref(false)
const editingRecipientId = ref<number | null>(null)
const recipientForm = ref({ name: '', channel_type: 'email', address: '', group_id: null as number | null })

const channelOptions = [
  { label: 'Email', value: 'email' },
  { label: '钉钉', value: 'dingtalk' },
]

const recipientColumns = [
  { title: '名称', key: 'name', ellipsis: true },
  { title: '渠道', key: 'channel_type', width: 80, render: (r: NotificationRecipient) => r.channel_type === 'dingtalk' ? '钉钉' : r.channel_type.toUpperCase() },
  { title: '地址', key: 'address', ellipsis: true },
  {
    title: '所属组', key: 'group_id', width: 120,
    render: (r: NotificationRecipient) => {
      const g = groups.value.find((x) => x.id === r.group_id)
      return g?.name || '-'
    },
  },
  {
    title: '操作', key: 'actions', width: 120,
    render: (row: NotificationRecipient) => h(NSpace, { size: 'small' }, () => [
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => openRecipientEdit(row) }, () => '编辑'),
      h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => handleRecipientDelete(row) }, () => '删除'),
    ]),
  },
]

// ── Data loading ─────────────────────────────────────────────────────────────

async function loadData() {
  loading.value = true
  try {
    const [gResp, rResp] = await Promise.all([fetchGroups(), fetchRecipients()])
    groups.value = gResp.data
    recipients.value = rResp.data
  } catch (_e) { /* ignore */ }
  finally { loading.value = false }
}

// ── Group CRUD ───────────────────────────────────────────────────────────────

function openGroupCreate() {
  editingGroupId.value = null
  groupForm.value = { name: '' }
  showGroupForm.value = true
}

function openGroupEdit(row: NotificationGroup) {
  editingGroupId.value = row.id
  groupForm.value = { name: row.name }
  showGroupForm.value = true
}

async function handleGroupSave() {
  if (!groupForm.value.name.trim()) { message.warning('请输入名称'); return }
  saving.value = true
  try {
    if (editingGroupId.value) {
      await updateGroup(editingGroupId.value, groupForm.value)
    } else {
      await createGroup(groupForm.value)
    }
    showGroupForm.value = false
    await loadData()
  } catch (_e) { /* ignore */ }
  finally { saving.value = false }
}

function handleGroupDelete(row: NotificationGroup) {
  dialog.warning({
    title: '确认删除', content: `确定要删除 "${row.name}" 吗？`, positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => { await deleteGroup(row.id); await loadData() },
  })
}

// ── Recipient CRUD ───────────────────────────────────────────────────────────

function openRecipientCreate() {
  editingRecipientId.value = null
  recipientForm.value = { name: '', channel_type: 'email', address: '', group_id: null }
  showRecipientForm.value = true
}

function openRecipientEdit(row: NotificationRecipient) {
  editingRecipientId.value = row.id
  recipientForm.value = { name: row.name, channel_type: row.channel_type, address: row.address, group_id: row.group_id }
  showRecipientForm.value = true
}

async function handleRecipientSave() {
  if (!recipientForm.value.name.trim() || !recipientForm.value.address.trim() || !recipientForm.value.group_id) {
    message.warning('请填写完整信息'); return
  }
  saving.value = true
  try {
    if (editingRecipientId.value) {
      await updateRecipient(editingRecipientId.value, recipientForm.value as any)
    } else {
      await createRecipient(recipientForm.value as any)
    }
    showRecipientForm.value = false
    await loadData()
  } catch (_e) { /* ignore */ }
  finally { saving.value = false }
}

function handleRecipientDelete(row: NotificationRecipient) {
  dialog.warning({
    title: '确认删除', content: `确定要删除 "${row.name}" 吗？`, positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => { await deleteRecipient(row.id); await loadData() },
  })
}

onMounted(loadData)
</script>
