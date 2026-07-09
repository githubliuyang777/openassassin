<template>
  <div style="max-width: 560px; margin: 0 auto">
    <n-card title="TOTP 双因素认证设置">
      <n-steps :current="currentStep" style="margin-bottom: 32px">
        <n-step title="邮箱验证" description="验证身份" />
        <n-step title="扫码绑定" description="配置认证器" />
        <n-step title="确认启用" description="保存备用码" />
      </n-steps>

      <!-- Step 1: Email verification -->
      <div v-if="currentStep === 0">
        <n-alert type="info" style="margin-bottom: 16px">
          TOTP 是一种基于时间的一次性密码验证方式。绑定后，登录时需要输入认证器 App（如 Google Authenticator、Microsoft Authenticator）显示的 6 位验证码。
        </n-alert>
        <p style="color: #666">验证码将发送至您的邮箱：<strong>{{ auth.user?.email || '未设置' }}</strong></p>
        <n-button type="primary" :loading="sending" block @click="sendEmail" :disabled="!auth.user?.email">
          {{ codeSent ? '重新发送验证码' : '发送验证码' }}
        </n-button>
        <div v-if="codeSent" style="margin-top: 16px">
          <n-input v-model:value="emailCode" placeholder="请输入6位验证码" maxlength="6"
            style="text-align: center; font-size: 20px; letter-spacing: 6px" />
          <n-button type="primary" block :loading="verifying" style="margin-top: 12px" @click="verifyEmail">
            验证
          </n-button>
        </div>
      </div>

      <!-- Step 2: Scan QR code -->
      <div v-if="currentStep === 1" style="text-align: center">
        <p style="color: #666; margin-bottom: 16px">请使用认证器 App 扫描以下二维码</p>
        <canvas ref="qrCanvas" style="margin-bottom: 12px"></canvas>
        <p style="color: #999; font-size: 13px; word-break: break-all">
          或手动输入密钥：<br/><code>{{ secret }}</code>
        </p>
        <div style="margin-top: 20px">
          <n-input v-model:value="confirmCode" placeholder="请输入认证器中的6位验证码" maxlength="6"
            style="text-align: center; font-size: 20px; letter-spacing: 6px" />
          <n-button type="primary" block :loading="confirming" style="margin-top: 12px" @click="confirmSetup">
            确认绑定
          </n-button>
        </div>
      </div>

      <!-- Step 3: Backup codes -->
      <div v-if="currentStep === 2">
        <n-alert type="warning" style="margin-bottom: 16px">
          请妥善保存以下备用码。每个备用码只能使用一次，用于在丢失认证器设备时登录。此页面关闭后将无法再次查看。
        </n-alert>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px">
          <div v-for="(code, i) in backupCodes" :key="i"
            style="background: #f5f7fa; padding: 8px 12px; border-radius: 4px; font-family: monospace; font-size: 15px; text-align: center">
            {{ code }}
          </div>
        </div>
        <n-button block @click="downloadBackupCodes">下载备用码（TXT）</n-button>
        <n-checkbox v-model:checked="savedConfirmed" style="margin-top: 16px">
          我已安全保存备用码
        </n-checkbox>
        <n-button type="primary" block :disabled="!savedConfirmed" style="margin-top: 12px" @click="finish">
          完成设置
        </n-button>
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  NCard, NSteps, NStep, NAlert, NInput, NButton, NCheckbox, useMessage,
} from 'naive-ui'
import QRCode from 'qrcode'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const currentStep = ref(0)
const sending = ref(false)
const verifying = ref(false)
const confirming = ref(false)
const codeSent = ref(false)
const emailCode = ref('')
const confirmCode = ref('')
const setupToken = ref('')
const secret = ref('')
const backupCodes = ref<string[]>([])
const savedConfirmed = ref(false)
const qrCanvas = ref<HTMLCanvasElement>()

async function sendEmail() {
  sending.value = true
  try {
    await auth.initMfaSetup()
    codeSent.value = true
    message.success('验证码已发送')
  } catch (e: any) {
    message.error(e.message || '发送失败')
  } finally {
    sending.value = false
  }
}

async function verifyEmail() {
  if (emailCode.value.length !== 6) {
    message.warning('请输入6位验证码')
    return
  }
  verifying.value = true
  try {
    const result = await auth.verifyMfaSetupEmail(emailCode.value)
    setupToken.value = result.setup_token
    // Extract secret from URI
    const url = new URL(result.provisioning_uri)
    const params = new URLSearchParams(url.search)
    secret.value = params.get('secret') || ''
    currentStep.value = 1
    await nextTick()
    if (qrCanvas.value) {
      await QRCode.toCanvas(qrCanvas.value, result.provisioning_uri, { width: 220 })
    }
  } catch (e: any) {
    message.error(e.message || '验证码错误')
  } finally {
    verifying.value = false
  }
}

async function confirmSetup() {
  if (confirmCode.value.length !== 6) {
    message.warning('请输入6位验证码')
    return
  }
  confirming.value = true
  try {
    const result = await auth.confirmMfaSetup(setupToken.value, confirmCode.value)
    backupCodes.value = result.backup_codes
    currentStep.value = 2
  } catch (e: any) {
    message.error(e.message || '验证失败')
  } finally {
    confirming.value = false
  }
}

function downloadBackupCodes() {
  const text = `openAssassin TOTP 备用码\n\n${backupCodes.value.join('\n')}\n\n每个备用码只能使用一次。`
  const blob = new Blob([text], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'openassassin-backup-codes.txt'
  a.click()
  URL.revokeObjectURL(url)
}

function finish() {
  message.success('TOTP 双因素认证已启用')
  router.push('/profile')
}
</script>
