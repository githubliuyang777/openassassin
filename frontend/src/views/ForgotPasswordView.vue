<template>
  <n-layout style="height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f7fa">
    <n-card style="width: 420px" title="重置密码">
      <!-- Step 1: send code -->
      <template v-if="step === 1">
        <n-form ref="emailFormRef" :model="emailForm" :rules="emailRules">
          <n-form-item path="email" label="邮箱地址">
            <n-input v-model:value="emailForm.email" placeholder="请输入注册邮箱" />
          </n-form-item>
        </n-form>
        <n-button type="primary" block :loading="sending" @click="handleSendCode">
          发送验证码
        </n-button>
      </template>

      <!-- Step 2: verify code and reset -->
      <template v-else>
        <n-form ref="resetFormRef" :model="resetForm" :rules="resetRules">
          <n-form-item path="code" label="验证码">
            <n-input v-model:value="resetForm.code" placeholder="请输入6位验证码" maxlength="6" />
          </n-form-item>
          <n-form-item path="newPassword" label="新密码">
            <n-input v-model:value="resetForm.newPassword" type="password" placeholder="至少6位" />
          </n-form-item>
        </n-form>
        <n-button type="primary" block :loading="resetting" @click="handleReset">
          重置密码
        </n-button>
      </template>

      <div style="text-align: center; margin-top: 16px">
        <n-button text @click="router.push('/login')">返回登录</n-button>
      </div>
    </n-card>
  </n-layout>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { NLayout, NCard, NForm, NFormItem, NInput, NButton, useMessage } from 'naive-ui'

const router = useRouter()
const message = useMessage()

const step = ref(1)
const sending = ref(false)
const resetting = ref(false)

const emailForm = ref({ email: '' })
const emailFormRef = ref()
const emailRules = {
  email: [
    { required: true, message: '请输入邮箱地址' },
    { type: 'email' as const, message: '请输入有效的邮箱地址', trigger: 'blur' },
  ],
}

const resetForm = ref({ code: '', newPassword: '' })
const resetFormRef = ref()
const resetRules = {
  code: [{ required: true, message: '请输入验证码' }],
  newPassword: [
    { required: true, message: '请输入新密码' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
}

async function handleSendCode() {
  const valid = await emailFormRef.value?.validate().catch(() => false)
  if (!valid) return
  sending.value = true
  try {
    const resp = await axios.post('/api/v1/auth/forgot-password', { email: emailForm.value.email })
    message.success(resp.data.message || '验证码已发送')
    step.value = 2
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.message || '发送失败')
  } finally {
    sending.value = false
  }
}

async function handleReset() {
  const valid = await resetFormRef.value?.validate().catch(() => false)
  if (!valid) return
  resetting.value = true
  try {
    await axios.post('/api/v1/auth/reset-password', {
      email: emailForm.value.email,
      code: resetForm.value.code,
      new_password: resetForm.value.newPassword,
    })
    message.success('密码重置成功，请使用新密码登录')
    router.push('/login')
  } catch (e: any) {
    message.error(e.response?.data?.detail || e.message || '重置失败')
  } finally {
    resetting.value = false
  }
}
</script>
