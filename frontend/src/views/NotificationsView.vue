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
    <n-card title="发送测试邮件">
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  NButton, NCard, NDescriptions, NDescriptionsItem, NTag,
  NForm, NFormItem, NInput, NAlert, NH2, NSpin,
} from 'naive-ui'
import { getSmtpStatus, sendTestEmail } from '@/api/notifications'

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
</script>
