import { api } from './client'

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
  days_remaining: number | null
  last_checked_at: string | null
  created_at: string | null
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

export function deleteDomain(id: number): Promise<void> {
  return api.delete(`/domains/${id}`)
}
