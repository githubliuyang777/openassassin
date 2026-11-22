import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { getSmtpStatus, sendTestEmail } from '@/api/notifications'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Notifications API', () => {
  it('fetches the SMTP status', async () => {
    const status = {
      configured: true,
      alert_configured: true,
      transactional_configured: true,
      alert_failover_enabled: true,
      active_circuit: null,
      primary: { configured: true, host: 'smtp-a.example.com', health: 'closed' },
      fallback: { configured: true, host: 'smtp-b.example.com', health: 'closed' },
    }
    ;(api.get as any).mockResolvedValue({ data: status })

    await expect(getSmtpStatus()).resolves.toEqual(status)
    expect(api.get).toHaveBeenCalledWith('/notifications/smtp-status')
  })

  it('sends a test email through automatic failover by default', async () => {
    ;(api.post as any).mockResolvedValue({
      data: { message: 'sent', provider: 'fallback', failover: true },
    })

    const result = await sendTestEmail('ops@example.com')

    expect(api.post).toHaveBeenCalledWith('/notifications/test-email', {
      email: 'ops@example.com',
      provider: 'auto',
    })
    expect(result.provider).toBe('fallback')
    expect(result.failover).toBe(true)
  })

  it('forwards an explicit provider selection', async () => {
    ;(api.post as any).mockResolvedValue({
      data: { message: 'sent', provider: 'primary', failover: false },
    })

    await sendTestEmail('ops@example.com', 'primary')

    expect(api.post).toHaveBeenCalledWith('/notifications/test-email', {
      email: 'ops@example.com',
      provider: 'primary',
    })
  })
})
