<template>
  <n-layout style="height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f7fa">
    <!-- Password step -->
    <n-card v-if="step === 'password'" style="width: 400px" title="openAssassin 登录">
      <n-form ref="formRef" :model="form" :rules="rules">
        <n-form-item path="username" label="用户名">
          <n-input v-model:value="form.username" placeholder="请输入用户名" />
        </n-form-item>
        <n-form-item path="password" label="密码">
          <n-input v-model:value="form.password" type="password" placeholder="请输入密码"
            @keyup.enter="handleLogin" />
        </n-form-item>
      </n-form>
      <n-button type="primary" block :loading="loading" @click="handleLogin">
        登录
      </n-button>
      <div style="text-align: center; margin-top: 16px">
        <n-button text type="primary" @click="router.push('/forgot-password')">忘记密码</n-button>
      </div>
    </n-card>

    <!-- MFA step -->
    <n-card v-else style="width: 400px" title="双因素认证">
      <template v-if="useRecovery">
        <p style="color: #666; margin-bottom: 16px">请输入备用码（格式：XXXX-XXXX-XX）</p>
        <n-input v-model:value="recoveryCode" placeholder="备用码" maxlength="12"
          style="margin-bottom: 16px" @keyup.enter="handleMfaSubmit" />
        <n-button type="primary" block :loading="loading" @click="handleMfaRecovery">
          验证备用码
        </n-button>
        <div style="text-align: center; margin-top: 12px">
          <n-button text @click="useRecovery = false">使用 TOTP 验证码</n-button>
        </div>
      </template>
      <template v-else>
        <p style="color: #666; margin-bottom: 16px">请输入认证器中的 6 位验证码</p>
        <n-input v-model:value="totpCode" placeholder="000000" maxlength="6"
          style="margin-bottom: 16px; font-size: 24px; text-align: center; letter-spacing: 8px"
          @keyup.enter="handleMfaSubmit" />
        <n-button type="primary" block :loading="loading" @click="handleMfaSubmit">
          验证
        </n-button>
        <div style="text-align: center; margin-top: 12px">
          <n-button text @click="useRecovery = true">使用备用码登录</n-button>
        </div>
      </template>
      <div style="text-align: center; margin-top: 8px">
        <n-button text size="small" @click="cancelMfa">返回登录</n-button>
      </div>
    </n-card>
  </n-layout>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { NLayout, NCard, NForm, NFormItem, NInput, NButton, useMessage } from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const form = ref({ username: 'admin', password: 'admin' })
const loading = ref(false)
const formRef = ref()
const step = ref<'password' | 'mfa'>('password')
const totpCode = ref('')
const useRecovery = ref(false)
const recoveryCode = ref('')

const rules = {
  username: [{ required: true, message: '请输入用户名' }],
  password: [{ required: true, message: '请输入密码' }],
}

function cancelMfa() {
  step.value = 'password'
  totpCode.value = ''
  recoveryCode.value = ''
  useRecovery.value = false
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const result = await auth.login(form.value.username, form.value.password)
    if (result.mfa_required) {
      step.value = 'mfa'
    } else {
      router.push('/')
    }
  } catch (e: any) {
    message.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}

async function handleMfaSubmit() {
  if (totpCode.value.length !== 6) {
    message.warning('请输入6位验证码')
    return
  }
  loading.value = true
  try {
    await auth.verifyMfa(totpCode.value)
    router.push('/')
  } catch (e: any) {
    message.error(e.message || '验证失败')
  } finally {
    loading.value = false
  }
}

async function handleMfaRecovery() {
  if (!recoveryCode.value.trim()) {
    message.warning('请输入备用码')
    return
  }
  loading.value = true
  try {
    await auth.verifyRecoveryCode(recoveryCode.value.trim())
    router.push('/')
  } catch (e: any) {
    message.error(e.message || '验证失败')
  } finally {
    loading.value = false
  }
}
</script>
