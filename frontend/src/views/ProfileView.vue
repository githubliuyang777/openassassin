<template>
  <div style="max-width: 480px">
    <n-h2>个人中心</n-h2>

    <n-card title="基本信息">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="用户名">
          <n-input :value="user?.username || ''" disabled />
        </n-form-item>
        <n-form-item label="角色">
          <n-input :value="user?.role || ''" disabled />
        </n-form-item>
      </n-form>
    </n-card>

    <n-card title="邮箱设置" style="margin-top: 16px">
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <n-form-item path="email" label="邮箱地址">
          <n-input v-model:value="form.email" placeholder="请输入邮箱地址" />
        </n-form-item>
      </n-form>
      <n-button type="primary" :loading="saving" @click="handleSave">
        保存
      </n-button>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  NButton, NCard, NForm, NFormItem, NInput, NH2, useMessage,
} from 'naive-ui'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'

const auth = useAuthStore()
const message = useMessage()
const user = ref(auth.user)
const saving = ref(false)
const formRef = ref()

const form = ref({ email: '' })
const rules = {
  email: [
    { type: 'email' as const, message: '请输入有效的邮箱地址', trigger: 'blur' },
  ],
}

onMounted(async () => {
  await auth.fetchMe()
  user.value = auth.user
  form.value.email = auth.user?.email || ''
})

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await api.put('/auth/me/email', { email: form.value.email })
    await auth.fetchMe()
    user.value = auth.user
    message.success('邮箱更新成功')
  } catch (e: any) {
    message.error(e.message || '更新失败')
  } finally {
    saving.value = false
  }
}
</script>
