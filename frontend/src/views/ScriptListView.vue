<template>
  <div>
    <n-space justify="space-between" style="margin-bottom: 16px">
      <n-h3 style="margin: 0">脚本管理</n-h3>
      <n-button type="primary" @click="router.push('/scripts/new')">
        <template #icon><n-icon><AddOutline /></n-icon></template>
        新建脚本
      </n-button>
    </n-space>

    <n-input v-model:value="search" placeholder="搜索脚本名称..." clearable style="width: 300px; margin-bottom: 16px"
      @update:value="onSearch" />

    <div v-if="checkedRowKeys.length" style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding: 8px 12px; background: #f0f7ff; border-radius: 4px">
      <span>已选 {{ checkedRowKeys.length }} 项</span>
      <BatchDeleteButton noun="脚本" :count="checkedRowKeys.length" :action="handleBatchDelete" />
      <n-button size="small" quaternary @click="checkedRowKeys = []">取消选择</n-button>
    </div>

    <n-data-table
      remote
      v-model:checked-row-keys="checkedRowKeys"
      :columns="columns"
      :data="scripts"
      :loading="loading"
      :row-key="(r: any) => r.id"
      :pagination="{ page: page, pageSize: pageSize, itemCount: total, onChange: onPageChange }"
    />

    <n-modal v-model:show="showDelete" preset="card" title="确认删除" style="width: 400px">
      <p>确定要删除脚本 "{{ deleting?.name }}" 吗？</p>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showDelete = false">取消</n-button>
          <n-button type="error" :loading="deletingLoading" @click="confirmDelete">删除</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  NH3, NSpace, NButton, NIcon, NInput, NDataTable, NModal, NTag, useMessage,
} from 'naive-ui'
import { AddOutline } from '@vicons/ionicons5'
import { fetchScripts, deleteScript, batchDeleteScripts, type Script } from '@/api/scripts'
import BatchDeleteButton from '@/components/BatchDeleteButton.vue'

const router = useRouter()
const message = useMessage()

const scripts = ref<Script[]>([])
const checkedRowKeys = ref<number[]>([])
const loading = ref(false)
const search = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showDelete = ref(false)
const deleting = ref<Script | null>(null)
const deletingLoading = ref(false)

const columns: any[] = [
  { type: 'selection' as const },
  { title: '名称', key: 'name', ellipsis: true },
  {
    title: '类型', key: 'type', width: 80,
    render: (r: any) => h(NTag, { type: r.type === 'python' ? 'info' : 'success', size: 'small' }, () => r.type),
  },
  { title: '描述', key: 'description', ellipsis: true },
  { title: '超时(s)', key: 'timeout', width: 80 },
  { title: '更新时间', key: 'updated_at', width: 170 },
  {
    title: '操作', key: 'actions', width: 280,
    render: (r: any) => h(NSpace, null, () => [
      h(NButton, { size: 'small', onClick: () => router.push(`/scripts/${r.id}/execute`) }, () => '执行'),
      h(NButton, { size: 'small', onClick: () => router.push(`/scripts/${r.id}/edit`) }, () => '编辑'),
      h(NButton, { size: 'small', type: 'error', onClick: () => { deleting.value = r; showDelete.value = true } }, () => '删除'),
    ]),
  },
]

async function loadScripts() {
  loading.value = true
  try {
    const res = await fetchScripts(page.value, pageSize.value, search.value)
    scripts.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  checkedRowKeys.value = []
  loadScripts()
}

function onPageChange(p: number) {
  page.value = p
  checkedRowKeys.value = []
  loadScripts()
}

async function confirmDelete() {
  if (!deleting.value) return
  deletingLoading.value = true
  try {
    const deletedId = deleting.value.id
    await deleteScript(deletedId)
    message.success('删除成功')
    checkingPageAfterDelete(1)
    checkedRowKeys.value = checkedRowKeys.value.filter(id => id !== deletedId)
    showDelete.value = false
    loadScripts()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    deletingLoading.value = false
  }
}

function checkingPageAfterDelete(deletedCount: number) {
  if (page.value > 1 && scripts.value.length <= deletedCount) {
    page.value -= 1
  }
}

async function handleBatchDelete() {
  try {
    const resp = await batchDeleteScripts([...checkedRowKeys.value])
    message.success(`已删除 ${resp.data.deleted} 个脚本`)
    if (resp.data.missing.length) {
      message.warning(`${resp.data.missing.length} 项已不存在，已跳过`)
    }
    checkingPageAfterDelete(resp.data.deleted)
    checkedRowKeys.value = []
    loadScripts()
  } catch (e: any) {
    message.error(e.message || '删除失败')
  }
}

onMounted(loadScripts)
</script>
