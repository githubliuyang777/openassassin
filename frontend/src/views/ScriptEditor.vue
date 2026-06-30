<template>
  <div style="max-width: 900px">
    <n-h3>{{ isEdit ? '编辑脚本' : '新建脚本' }}</n-h3>

    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
      <n-grid :cols="2" :x-gap="16">
        <n-grid-item>
          <n-form-item path="name" label="名称">
            <n-input v-model:value="form.name" placeholder="脚本名称" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item path="type" label="类型">
            <n-select v-model:value="form.type" :options="typeOptions" placeholder="选择脚本类型" />
          </n-form-item>
        </n-grid-item>
      </n-grid>
      <n-form-item path="description" label="描述">
        <n-input v-model:value="form.description" placeholder="脚本用途描述" />
      </n-form-item>
      <n-grid :cols="2" :x-gap="16">
        <n-grid-item>
          <n-form-item path="timeout" label="超时时间(秒)">
            <n-input-number v-model:value="form.timeout" :min="1" :max="3600" />
          </n-form-item>
        </n-grid-item>
      </n-grid>
      <n-form-item path="content" label="脚本内容">
        <n-input type="textarea" v-model:value="form.content" :rows="14"
          :placeholder="form.type === 'python' ? 'print(\"hello ops\")' : '#!/bin/sh\necho \"hello ops\"'"
          style="font-family: monospace" />
      </n-form-item>
    </n-form>

    <n-space>
      <n-button type="primary" :loading="saving" @click="handleSave">保存</n-button>
      <n-button @click="router.back()">取消</n-button>
    </n-space>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  NH3, NForm, NFormItem, NInput, NInputNumber, NSelect,
  NButton, NSpace, NGrid, NGridItem, useMessage,
} from 'naive-ui'
import { fetchScript, createScript, updateScript } from '@/api/scripts'

const router = useRouter()
const route = useRoute()
const message = useMessage()

const isEdit = computed(() => !!route.params.id)

const typeOptions = [
  { label: 'Shell', value: 'shell' },
  { label: 'Python', value: 'python' },
]

const form = ref({
  name: '',
  description: '',
  type: 'shell',
  content: '',
  timeout: 300,
})

const rules = {
  name: [{ required: true, message: '请输入脚本名称' }],
  type: [{ required: true, message: '请选择类型' }],
  content: [{ required: true, message: '请输入脚本内容' }],
}

const saving = ref(false)
const formRef = ref()

onMounted(async () => {
  if (!isEdit.value) return
  try {
    const res = await fetchScript(Number(route.params.id))
    Object.assign(form.value, res.data)
  } catch (e: any) {
    message.error(e.message)
  }
})

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value) {
      await updateScript(Number(route.params.id), form.value)
      message.success('更新成功')
    } else {
      await createScript(form.value)
      message.success('创建成功')
    }
    router.push('/scripts')
  } catch (e: any) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}
</script>
