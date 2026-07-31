<template>
  <div style="max-width: 640px">
    <n-h2>消息通知</n-h2>

    <!-- SMTP Status -->
    <n-card title="SMTP 配置状态" style="margin-bottom: 24px">
      <n-descriptions v-if="smtp" bordered :column="1" label-placement="left">
        <n-descriptions-item label="状态">
          <n-tag :type="smtp.configured ? 'success' : 'error'">
            {{ smtp.configured ? '已配置' : '未配置' }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="SMTP 服务器">{{ smtp.host || '-' }}</n-descriptions-item>
        <n-descriptions-item label="端口">{{ smtp.port || '-' }}</n-descriptions-item>
        <n-descriptions-item label="发件人">{{ smtp.from || '-' }}</n-descriptions-item>
        <n-descriptions-item label="TLS">{{ smtp.use_tls ? '启用' : '未启用' }}</n-descriptions-item>
      </n-descriptions>
      <n-spin v-else size="small" />
    </n-card>

    <!-- Test Email -->
    <n-card title="发送测试邮件" style="margin-bottom: 24px">
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <n-form-item path="email" label="收件人邮箱地址">
          <n-input v-model:value="form.email" placeholder="请输入收件人邮箱，例如 user@example.com" />
        </n-form-item>
      </n-form>
      <n-button type="primary" :loading="sending" @click="handleSend">
        发送测试邮件
      </n-button>
      <n-alert v-if="result" :type="result.type" :title="result.title" style="margin-top: 16px" closable @close="result = null">
        {{ result.message }}
      </n-alert>
    </n-card>

    <!-- DingTalk Config Status -->
    <n-card title="钉钉配置状态" style="margin-bottom: 24px">
      <n-descriptions v-if="dingtalkStatus" bordered :column="1" label-placement="left">
        <n-descriptions-item label="状态">
          <n-tag :type="dingtalkStatus.configured ? 'success' : 'error'">
            {{ dingtalkStatus.configured ? '已配置' : '未配置' }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="启用">
          <n-tag :type="dingtalkStatus.enabled ? 'success' : 'default'">
            {{ dingtalkStatus.enabled ? '已启用' : '未启用' }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="Webhook 地址">
          {{ dingtalkStatus.webhook_masked || '-' }}
        </n-descriptions-item>
      </n-descriptions>
      <n-spin v-else size="small" />
    </n-card>

    <!-- DingTalk Config Form -->
    <n-card title="钉钉配置" style="margin-bottom: 24px">
      <n-form ref="dtFormRef" :model="dtForm" label-placement="top">
        <n-form-item path="webhook_url" label="Webhook 地址">
          <n-input v-model:value="dtForm.webhook_url" placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." />
        </n-form-item>
        <n-form-item path="secret" label="加签密钥（可选）">
          <n-input v-model:value="dtForm.secret" type="password" show-password-on="click" placeholder="SEC 开头的加签密钥，机器人开启加签时必填" />
        </n-form-item>
        <n-form-item path="is_enabled" label="启用钉钉通知">
          <n-switch v-model:value="dtForm.is_enabled" />
        </n-form-item>
      </n-form>
      <n-space>
        <n-button type="primary" :loading="savingDt" @click="handleSaveDtConfig">保存配置</n-button>
        <n-button :loading="testingDt" @click="handleTestDt">测试连接</n-button>
      </n-space>
      <n-alert v-if="dtResult" :type="dtResult.type" :title="dtResult.title" style="margin-top: 16px" closable @close="dtResult = null">
        {{ dtResult.message }}
      </n-alert>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  NButton, NCard, NDescriptions, NDescriptionsItem, NTag, NSpace,
  NForm, NFormItem, NInput, NAlert, NH2, NSpin, NSwitch,
} from 'naive-ui'
import { getSmtpStatus, sendTestEmail, getDingTalkStatus, getDingTalkConfig, updateDingTalkConfig, testDingTalk } from '@/api/notifications'

const formRef = ref()
const sending = ref(false)
const smtp = ref<any>(null)
const result = ref<{ type: 'success' | 'error'; title: string; message: string } | null>(null)

const form = ref({ email: '' })
const rules = {
  email: [
    { required: true, message: '请输入收件人邮箱' },
    { type: 'email' as const, message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
}

onMounted(async () => {
  try {
    smtp.value = await getSmtpStatus()
  } catch {
    // ignore
  }
  await loadDingTalk()
})

async function handleSend() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  sending.value = true
  result.value = null
  try {
    const data = await sendTestEmail(form.value.email)
    result.value = { type: 'success', title: '发送成功', message: data.message }
  } catch (e: any) {
    result.value = { type: 'error', title: '发送失败', message: e.message || '未知错误' }
  } finally {
    sending.value = false
  }
}

// ── DingTalk ──────────────────────────────────────────────────────────────────

const dtFormRef = ref()
const savingDt = ref(false)
const testingDt = ref(false)
const dingtalkStatus = ref<any>(null)
const dtResult = ref<{ type: 'success' | 'error'; title: string; message: string } | null>(null)

const dtForm = ref({
  webhook_url: '',
  secret: '',
  is_enabled: false,
})

async function loadDingTalk() {
  try {
    const [status, config] = await Promise.all([
      getDingTalkStatus(),
      getDingTalkConfig(),
    ])
    dingtalkStatus.value = status
    dtForm.value.webhook_url = config.webhook_url || ''
    dtForm.value.is_enabled = config.is_enabled || false
  } catch {
    // ignore
  }
}

async function handleSaveDtConfig() {
  savingDt.value = true
  dtResult.value = null
  try {
    await updateDingTalkConfig({
      webhook_url: dtForm.value.webhook_url,
      secret: dtForm.value.secret || undefined,
      is_enabled: dtForm.value.is_enabled,
    })
    dtResult.value = { type: 'success', title: '保存成功', message: '钉钉配置已更新' }
    await loadDingTalk()
  } catch (e: any) {
    dtResult.value = { type: 'error', title: '保存失败', message: e.message || '未知错误' }
  } finally {
    savingDt.value = false
  }
}

async function handleTestDt() {
  testingDt.value = true
  dtResult.value = null
  try {
    const data = await testDingTalk()
    dtResult.value = { type: 'success', title: '发送成功', message: data.message }
  } catch (e: any) {
    dtResult.value = { type: 'error', title: '发送失败', message: e.message || '未知错误' }
  } finally {
    testingDt.value = false
  }
}
</script>
