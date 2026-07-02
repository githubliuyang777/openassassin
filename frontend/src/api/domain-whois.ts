import { api } from './client'

export interface DomainWhoisInfo {
  id: number
  domain: string
  whois_expiry_date: string | null
  whois_creation_date: string | null
  whois_registrar: string | null
  whois_statuses: string | null
  whois_nameservers: string | null
  days_remaining: number | null
  last_checked_at: string | null
  created_at: string | null
}

export function fetchWhoisDomains(): Promise<{ data: DomainWhoisInfo[] }> {
  return api.get('/whois-domains')
}

export function addWhoisDomain(domain: string): Promise<{ data: DomainWhoisInfo }> {
  return api.post('/whois-domains', { domain })
}

export function batchImportWhoisDomains(domains: string[]): Promise<{ data: { result: { added: number; skipped: number; invalid: number }; domains: DomainWhoisInfo[] } }> {
  return api.post('/whois-domains/batch-import', { domains })
}

export function refreshAllWhoisDomains(): Promise<{ data: { refreshed: number; domains: DomainWhoisInfo[] } }> {
  return api.post('/whois-domains/refresh')
}

export function refreshWhoisDomain(id: number): Promise<{ data: DomainWhoisInfo }> {
  return api.post(`/whois-domains/${id}/refresh`)
}

export function deleteWhoisDomain(id: number): Promise<void> {
  return api.delete(`/whois-domains/${id}`)
}
