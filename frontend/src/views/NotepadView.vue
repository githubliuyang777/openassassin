<template>
  <div style="display: flex; gap: 16px; height: calc(100vh - 160px)">
    <!-- Left: list panel -->
    <div style="width: 380px; display: flex; flex-direction: column; gap: 12px; flex-shrink: 0">
      <n-space justify="space-between" align="center">
        <n-h3 style="margin: 0">记事本</n-h3>
        <n-button type="primary" size="small" @click="startNew">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          新建
        </n-button>
      </n-space>
      <n-input
        v-model:value="search"
        placeholder="搜索标题或内容..."
        clearable
        @update:value="loadList"
      />
      <n-data-table
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(r: Notepad) => r.id"
        :pagination="{ page, pageSize, itemCount: total, prefix: () => `共 ${total} 条` }"
        size="small"
        max-height="calc(100vh - 340px)"
        virtual-scroll
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
    </div>

    <!-- Right: editor panel -->
    <div style="flex: 1; display: flex; flex-direction: column; gap: 12px; min-width: 0">
      <div style="display: flex; align-items: center; gap: 8px">
        <n-input
          v-model:value="title"
          placeholder="标题"
          size="large"
          style="flex: 1; font-weight: 600"
        />
        <n-button type="primary" :loading="saving" @click="handleSave">
          {{ editingId ? '保存' : '创建' }}
        </n-button>
        <n-button v-if="editingId" @click="startNew">取消</n-button>
      </div>
      <div class="editor-wrapper">
        <div ref="lineNumbersRef" class="line-numbers">
          <div v-for="n in lineCount" :key="n" class="line-num">{{ n }}</div>
        </div>
        <textarea
          ref="textareaRef"
          v-model="content"
          class="editor-textarea"
          placeholder="在此输入内容..."
          @scroll="syncScroll"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted, nextTick } from 'vue'
import { useMessage, useDialog, NTag, NButton, NIcon, NSpace, NDataTable, NH3, NInput } from 'naive-ui'
import { AddOutline } from '@vicons/ionicons5'
import {
  fetchNotepads, fetchNotepad, createNotepad, updateNotepad, deleteNotepad,
} from '@/api/notepads'
import type { Notepad } from '@/api/notepads'

const message = useMessage()
const dialog = useDialog()

// List state
const items = ref<Notepad[]>([])
const loading = ref(false)
const search = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// Editor state
const editingId = ref<number | null>(null)
const title = ref('')
const content = ref('')
const saving = ref(false)
const textareaRef = ref<HTMLTextAreaElement>()
const lineNumbersRef = ref<HTMLDivElement>()

const lineCount = computed(() => {
  const lines = content.value.split('\n').length
  return Math.max(lines, 1)
})

function syncScroll() {
  if (lineNumbersRef.value && textareaRef.value) {
    lineNumbersRef.value.scrollTop = textareaRef.value.scrollTop
  }
}

const columns = [
  { title: '标题', key: 'title', ellipsis: { tooltip: true }, width: 200 },
  {
    title: '更新时间', key: 'updated_at', width: 130,
    render: (r: Notepad) => {
      if (!r.updated_at) return '-'
      return new Date(r.updated_at).toLocaleString('zh-CN', {
        month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
      })
    },
  },
  {
    title: '', key: 'actions', width: 90,
    render: (row: Notepad) => h(NSpace, { size: 'small' }, () => [
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEdit(row) }, () => '编辑'),
      h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => handleDelete(row) }, () => '删除'),
    ]),
  },
]

async function loadList() {
  loading.value = true
  try {
    const resp = await fetchNotepads(page.value, pageSize.value, search.value)
    items.value = resp.data.items
    total.value = resp.data.total
  } catch (_e) { /* ignore */ }
  finally { loading.value = false }
}

function onPageChange(p: number) { page.value = p; loadList() }
function onPageSizeChange(ps: number) { pageSize.value = ps; page.value = 1; loadList() }

function startNew() {
  editingId.value = null
  title.value = ''
  content.value = ''
  nextTick(() => textareaRef.value?.focus())
}

function openEdit(row: Notepad) {
  editingId.value = row.id
  title.value = row.title
  content.value = row.content
  nextTick(() => textareaRef.value?.focus())
}

async function handleSave() {
  if (!title.value.trim()) {
    message.warning('请输入标题')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateNotepad(editingId.value, { title: title.value, content: content.value })
      message.success('保存成功')
    } else {
      await createNotepad({ title: title.value, content: content.value })
      message.success('创建成功')
    }
    await loadList()
  } catch (_e) { /* ignore */ }
  finally { saving.value = false }
}

function handleDelete(row: Notepad) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除 "${row.title}" 吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteNotepad(row.id)
        message.success('删除成功')
        if (editingId.value === row.id) startNew()
        await loadList()
      } catch (_e) { /* ignore */ }
    },
  })
}

onMounted(loadList)
</script>

<style scoped>
.editor-wrapper {
  flex: 1;
  display: flex;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
  background: #fff;
}
.line-numbers {
  width: 56px;
  background: #f5f5f5;
  color: #999;
  text-align: right;
  padding: 10px 8px 10px 4px;
  font-family: Menlo, Monaco, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  overflow: hidden;
  user-select: none;
  border-right: 1px solid #e0e0e0;
}
.line-num {
  line-height: 1.6;
}
.editor-textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  padding: 10px;
  font-family: Menlo, Monaco, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  tab-size: 4;
  overflow-y: auto;
}
</style>
