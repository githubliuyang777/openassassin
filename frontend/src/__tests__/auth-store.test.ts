import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/client', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

import { api } from '@/api/client'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.clearAllMocks()
})

describe('Auth Store', () => {
  it('starts with no token', () => {
    const store = useAuthStore()
    expect(store.token).toBe('')
    expect(store.isLoggedIn).toBe(false)
    expect(store.user).toBeNull()
  })

  it('login sets token and fetches user', async () => {
    const store = useAuthStore()
    const mockToken = 'jwt-token-123'
    const mockUser = { id: 1, username: 'admin', role: 'admin' }
    ;(api.post as any).mockResolvedValue({ data: { access_token: mockToken } })
    ;(api.get as any).mockResolvedValue({ data: mockUser })

    await store.login('admin', 'admin')

    expect(api.post).toHaveBeenCalledWith('/auth/login', { username: 'admin', password: 'admin' })
    expect(api.get).toHaveBeenCalledWith('/auth/me')
    expect(store.token).toBe(mockToken)
    expect(store.isLoggedIn).toBe(true)
    expect(store.user).toEqual(mockUser)
    expect(localStorage.getItem('token')).toBe(mockToken)
  })

  it('logout clears state', () => {
    const store = useAuthStore()
    store.token = 'some-token'
    store.user = { id: 1, username: 'admin', role: 'admin' }
    localStorage.setItem('token', 'some-token')

    store.logout()

    expect(store.token).toBe('')
    expect(store.user).toBeNull()
    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('isLoggedIn reflects token presence', () => {
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
    store.token = 'abc'
    expect(store.isLoggedIn).toBe(true)
  })

  it('fetchMe does nothing without token', async () => {
    const store = useAuthStore()
    await store.fetchMe()
    expect(api.get).not.toHaveBeenCalled()
    expect(store.user).toBeNull()
  })
})
