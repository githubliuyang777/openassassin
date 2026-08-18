import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<any>(null)
  const mfaToken = ref('')

  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const res = await api.post('/auth/login', { username, password })
    const data = res.data as any
    if (data.mfa_token) {
      mfaToken.value = data.mfa_token
      return { mfa_required: true }
    }
    token.value = data.access_token
    localStorage.setItem('token', token.value)
    await fetchMe()
    return { mfa_required: false }
  }

  async function verifyMfa(totpCode: string) {
    const res = await api.post('/auth/mfa/verify', { totp_code: totpCode }, {
      headers: { Authorization: `Bearer ${mfaToken.value}` },
    })
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    mfaToken.value = ''
    await fetchMe()
  }

  async function verifyRecoveryCode(recoveryCode: string) {
    const res = await api.post('/auth/mfa/recovery', { recovery_code: recoveryCode }, {
      headers: { Authorization: `Bearer ${mfaToken.value}` },
    })
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    mfaToken.value = ''
    await fetchMe()
  }

  async function logout() {
    try { await api.post('/auth/logout') } catch (_e) {}
    token.value = ''
    user.value = null
    mfaToken.value = ''
    localStorage.removeItem('token')
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    await api.put('/auth/password', { old_password: oldPassword, new_password: newPassword })
    await logout()
  }

  async function initMfaSetup() {
    await api.post('/auth/mfa/setup/init')
  }

  async function verifyMfaSetupEmail(code: string) {
    const res = await api.post('/auth/mfa/setup/verify-email', { email_code: code })
    return res.data as { provisioning_uri: string; setup_token: string }
  }

  async function confirmMfaSetup(setupToken: string, totpCode: string) {
    const res = await api.post('/auth/mfa/setup/confirm', {
      totp_code: totpCode,
    }, {
      headers: { Authorization: `Bearer ${setupToken}` },
    })
    return res.data as { backup_codes: string[]; message: string }
  }

  async function disableMfa(password: string) {
    await api.post('/auth/mfa/disable', { password })
  }

  async function fetchMfaStatus() {
    const res = await api.get('/auth/mfa/status')
    return res.data as { totp_enabled: boolean; backup_codes_remaining: number }
  }

  async function fetchMe() {
    if (!token.value) return
    const res = await api.get('/auth/me')
    user.value = res.data
  }

  return {
    token, user, isLoggedIn,
    login, verifyMfa, verifyRecoveryCode, logout, changePassword,
    initMfaSetup, verifyMfaSetupEmail, confirmMfaSetup, disableMfa,
    fetchMfaStatus, fetchMe,
  }
})
