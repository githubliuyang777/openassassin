import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      router.push('/login')
    }
    const msg = err.response?.data?.detail || err.message || '网络错误'
    return Promise.reject(new Error(msg))
  },
)
