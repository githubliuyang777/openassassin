import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<{ id: number; username: string; role: string; email: string } | null>(null)

  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const res = await api.post('/auth/login', { username, password })
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    await fetchMe()
  }

  async function fetchMe() {
    if (!token.value) return
    const res = await api.get('/auth/me')
    user.value = res.data
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    await api.put('/auth/password', { old_password: oldPassword, new_password: newPassword })
    logout()
  }

  return { token, user, isLoggedIn, login, fetchMe, logout, changePassword }
})
