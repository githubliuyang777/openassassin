import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { fetchVersion } from '@/api/system'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('System API', () => {
  it('fetches the website version from the authenticated endpoint', async () => {
    ;(api.get as any).mockResolvedValue({ data: { version: 'v1.2.3' } })

    const result = await fetchVersion()

    expect(api.get).toHaveBeenCalledWith('/system/version')
    expect(result).toEqual({ version: 'v1.2.3' })
  })
})
