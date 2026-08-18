import { api } from './client'

export interface SiteMonitorSummary {
  id: number
  name: string
  target: string
  is_up: boolean
  response_ms: number | null
}

export interface SiteMonitorOverview {
  total: number
  up: number
  down: number
  items: SiteMonitorSummary[]
}

export interface DomainCertSummary {
  id: number
  domain: string
  ssl_expired: boolean
  days_remaining: number | null
}

export interface DomainCertOverview {
  total: number
  valid: number
  expiring: number
  expired: number
  items: DomainCertSummary[]
}

export interface DomainWhoisSummary {
  id: number
  domain: string
  days_remaining: number | null
}

export interface DomainWhoisOverview {
  total: number
  valid: number
  expiring: number
  expired: number
  items: DomainWhoisSummary[]
}

export interface MonitorSummary {
  site_monitors: SiteMonitorOverview
  domain_certs: DomainCertOverview
  domain_whois: DomainWhoisOverview
}

export function fetchMonitorSummary() {
  return api.get<MonitorSummary>('/overview/monitor-summary')
}
