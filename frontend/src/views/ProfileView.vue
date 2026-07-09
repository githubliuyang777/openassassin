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

    <n-card title="安全设置" style="margin-top: 16px">
      <n-descriptions :column="1" label-placement="left">
        <n-descriptions-item label="TOTP 双因素认证">
          <n-tag :type="totpEnabled ? 'success' : 'default'">
            {{ totpEnabled ? '已启用' : '未启用' }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item v-if="totpEnabled" label="剩余备用码">
          {{ backupCodesRemaining }} 个
        </n-descriptions-item>
      </n-descriptions>
      <n-space style="margin-top: 12px">
        <n-button v-if="!totpEnabled" type="primary" @click="router.push('/mfa-setup')">
          设置 TOTP
        </n-button>
        <n-button v-if="totpEnabled" type="warning" @click="showDisableModal = true">
          禁用 TOTP
        </n-button>
      </n-space>
    </n-card>

    <!-- Disable TOTP modal -->
    <n-modal v-model:show="showDisableModal" preset="card" title="禁用双因素认证" style="width: 400px">
      <n-form-item label="请输入密码确认">
        <n-input v-model:value="disablePassword" type="password" placeholder="请输入密码" />
      </n-form-item>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showDisableModal = false">取消</n-button>
          <n-button type="warning" :loading="disabling" @click="handleDisableMfa">确认禁用</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton, NCard, NForm, NFormItem, NInput, NH2, NSpace, NTag, NDescriptions,
  NDescriptionsItem, NModal, useMessage,
} from 'naive-ui'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const user = ref(auth.user)
const saving = ref(false)
const formRef = ref()

const totpEnabled = ref(false)
const backupCodesRemaining = ref(0)
const showDisableModal = ref(false)
const disablePassword = ref('')
const disabling = ref(false)

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
  try {
    const status = await auth.fetchMfaStatus()
    totpEnabled.value = status.totp_enabled
    backupCodesRemaining.value = status.backup_codes_remaining
  } catch (_e) { /* ignore */ }
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

async function handleDisableMfa() {
  if (!disablePassword.value) {
    message.warning('请输入密码')
    return
  }
  disabling.value = true
  try {
    await auth.disableMfa(disablePassword.value)
    totpEnabled.value = false
    backupCodesRemaining.value = 0
    showDisableModal.value = false
    disablePassword.value = ''
    message.success('TOTP 已禁用')
  } catch (e: any) {
    message.error(e.message || '禁用失败')
  } finally {
    disabling.value = false
  }
}
</script>
