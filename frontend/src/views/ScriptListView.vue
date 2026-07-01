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
      @update:value="loadScripts" />

    <n-data-table :columns="columns" :data="scripts" :loading="loading" :row-key="(r: any) => r.id"
      :pagination="{ page: page, pageSize: pageSize, itemCount: total, onChange: onPageChange }" />

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
import { fetchScripts, deleteScript, type Script } from '@/api/scripts'

const router = useRouter()
const message = useMessage()

const scripts = ref<Script[]>([])
const loading = ref(false)
const search = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showDelete = ref(false)
const deleting = ref<Script | null>(null)
const deletingLoading = ref(false)

const columns: any[] = [
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

function onPageChange(p: number) {
  page.value = p
  loadScripts()
}

async function confirmDelete() {
  if (!deleting.value) return
  deletingLoading.value = true
  try {
    await deleteScript(deleting.value.id)
    message.success('删除成功')
    showDelete.value = false
    loadScripts()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    deletingLoading.value = false
  }
}

onMounted(loadScripts)
</script>
