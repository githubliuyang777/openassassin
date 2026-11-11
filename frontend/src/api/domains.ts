import { api } from './client'

export interface DomainProviderConfig {
  panel_id?: number
  site_name?: string
}

export interface DomainInfo {
  id: number
  domain: string
  port: number
  ssl_subject: string | null
  ssl_issuer: string | null
  ssl_not_before: string | null
  ssl_not_after: string | null
  ssl_expired: boolean
  alert_enabled: boolean
  notification_group_id: number | null
  cert_provider: string
  cert_provider_config: DomainProviderConfig
  cert_auto_renew: boolean
  last_renew_attempt_at: string | null
  last_renew_status: string
  last_renew_error: string
  days_remaining: number | null
  last_checked_at: string | null
  created_at: string | null
}

export interface DomainUpdate {
  port?: number
  alert_enabled?: boolean
  notification_group_id?: number | null
  cert_provider?: string
  cert_provider_config?: DomainProviderConfig
  cert_auto_renew?: boolean
}

export function fetchDomains(): Promise<{ data: DomainInfo[] }> {
  return api.get('/domains')
}

export function addDomain(domain: string, port: number = 443): Promise<{ data: DomainInfo }> {
  return api.post('/domains', { domain, port })
}

export function batchImportDomains(domains: string[]): Promise<{ data: { result: { added: number; skipped: number; invalid: number }; domains: DomainInfo[] } }> {
  return api.post('/domains/batch-import', { domains })
}

export function refreshAllDomains(): Promise<{ data: { refreshed: number; domains: DomainInfo[] } }> {
  return api.post('/domains/refresh')
}

export function refreshDomain(id: number): Promise<{ data: DomainInfo }> {
  return api.post(`/domains/${id}/refresh`)
}

export function toggleDomainAlert(id: number): Promise<{ data: DomainInfo }> {
  return api.put(`/domains/${id}/toggle-alert`)
}

export function batchToggleDomainAlert(ids: number[], enabled: boolean): Promise<{ data: { updated: number; domains: DomainInfo[] } }> {
  return api.post('/domains/batch-toggle-alert', { ids, enabled })
}

export function batchSetNotificationGroup(ids: number[], notification_group_id: number | null): Promise<{ data: { updated: number } }> {
  return api.post('/domains/batch-set-notification-group', { ids, notification_group_id })
}

export function updateDomain(id: number, data: DomainUpdate): Promise<{ data: DomainInfo }> {
  return api.put(`/domains/${id}`, data)
}

export function renewDomainCert(id: number): Promise<{ data: { message: string } }> {
  return api.post(`/domains/${id}/renew-cert`)
}

export function deleteDomain(id: number): Promise<void> {
  return api.delete(`/domains/${id}`)
}
