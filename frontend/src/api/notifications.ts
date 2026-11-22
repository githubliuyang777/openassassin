import { api } from './client'

export type SmtpProviderName = 'primary' | 'fallback'
export type SmtpTestProvider = 'auto' | SmtpProviderName
export type CircuitHealth = 'closed' | 'open' | 'half_open'

export interface SmtpProviderStatus {
  configured: boolean
  host: string | null
  port: number | null
  from: string | null
  use_tls: boolean
  health: CircuitHealth
  last_error: string | null
  last_success_at: string | null
}

export interface SmtpStatus {
  configured: boolean
  alert_configured: boolean
  transactional_configured: boolean
  primary: SmtpProviderStatus
  fallback: SmtpProviderStatus
  alert_failover_enabled: boolean
  active_circuit: SmtpProviderName | null
  host: string | null
  port: number | null
  from: string | null
  use_tls: boolean
}

export interface TestEmailResult {
  message: string
  provider: SmtpProviderName | null
  failover: boolean
}

export function sendTestEmail(
  email: string,
  provider: SmtpTestProvider = 'auto',
): Promise<TestEmailResult> {
  return api.post('/notifications/test-email', { email, provider }).then(r => r.data)
}

export function getSmtpStatus(): Promise<SmtpStatus> {
  return api.get('/notifications/smtp-status').then(r => r.data)
}

export {
  getDingTalkConfig,
  updateDingTalkConfig,
  getDingTalkStatus,
  testDingTalk,
} from './dingtalk'
