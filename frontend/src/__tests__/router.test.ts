import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { defineComponent, h } from 'vue'

const Stub = (name: string) => defineComponent({ name, render: () => h('div', name) })

vi.mock('@/views/LoginView.vue', () => ({ default: Stub('LoginView') }))
vi.mock('@/layouts/MainLayout.vue', () => ({ default: Stub('MainLayout') }))
vi.mock('@/views/DashboardView.vue', () => ({ default: Stub('DashboardView') }))

describe('Router guards', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('guest routes are accessible without token', async () => {
    const router = (await import('@/router/index')).default
    const store = useAuthStore()
    store.token = ''

    await router.push('/login')
    expect(router.currentRoute.value.name).toBe('Login')
  })

  it('non-guest routes redirect to /login without token', async () => {
    const router = (await import('@/router/index')).default
    const store = useAuthStore()
    store.token = ''

    await router.push('/dashboard')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('non-guest routes are accessible with token', async () => {
    const router = (await import('@/router/index')).default
    const store = useAuthStore()
    store.token = 'valid-token'

    await router.push('/dashboard')
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('authenticated user can still access login', async () => {
    const router = (await import('@/router/index')).default
    const store = useAuthStore()
    store.token = 'valid-token'

    await router.push('/login')
    expect(router.currentRoute.value.name).toBe('Login')
  })
})
