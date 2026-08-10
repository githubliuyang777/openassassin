import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<any>(null)

  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const res = await api.post('/auth/login', { username, password })
    const data = res.data as any
    if (data.mfa_token) {
      return { mfa_token: data.mfa_token }
    }
    token.value = data.access_token
    localStorage.setItem('token', token.value)
    await fetchMe()
    return {}
  }

  async function mfaVerify(mfaToken: string, totpCode: string) {
    const res = await api.post('/auth/mfa/verify', { totp_code: totpCode }, {
      headers: { Authorization: `Bearer ${mfaToken}` },
    })
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    await fetchMe()
  }

  async function mfaRecovery(mfaToken: string, recoveryCode: string) {
    const res = await api.post('/auth/mfa/recovery', { recovery_code: recoveryCode }, {
      headers: { Authorization: `Bearer ${mfaToken}` },
    })
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    await fetchMe()
  }

  async function logout() {
    try { await api.post('/auth/logout') } catch (_e) {}
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    await api.put('/auth/password', { old_password: oldPassword, new_password: newPassword })
  }

  async function initMfaSetup() {
    await api.post('/auth/mfa/setup/init')
  }

  async function verifyMfaEmail(code: string) {
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

  async function fetchMe() {
    if (!token.value) return
    const res = await api.get('/auth/me')
    user.value = res.data
  }

  return {
    token, user, isLoggedIn,
    login, mfaVerify, mfaRecovery, logout, changePassword,
    initMfaSetup, verifyMfaEmail, confirmMfaSetup, disableMfa,
    fetchMe,
  }
})
