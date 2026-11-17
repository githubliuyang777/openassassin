import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { buildTraceUrl, fetchTracingInfo, fetchVersion } from '@/api/system'

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

  it('fetches tracing config from the authenticated endpoint', async () => {
    ;(api.get as any).mockResolvedValue({
      data: { enabled: true, ui_url: 'https://jaeger.example.com' },
    })

    const result = await fetchTracingInfo()

    expect(api.get).toHaveBeenCalledWith('/system/tracing')
    expect(result).toEqual({ enabled: true, ui_url: 'https://jaeger.example.com' })
  })

  it('builds a Jaeger trace link only for valid input', () => {
    const id = 'a'.repeat(32)

    expect(buildTraceUrl('https://jaeger.example.com/', id)).toBe(
      `https://jaeger.example.com/trace/${id}`,
    )
    expect(buildTraceUrl('', id)).toBe('')
    expect(buildTraceUrl('https://jaeger.example.com', 'not-hex')).toBe('')
  })
})
