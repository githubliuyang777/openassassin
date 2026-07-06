import { api } from './client'

export interface SiteMonitor {
  id: number
  name: string
  target: string
  monitor_type: string
  http_method: string
  expected_status_codes: string
  timeout: number
  retries: number
  check_interval: number
  alert_enabled: boolean
  is_up: boolean
  last_checked_at: string | null
  last_response_ms: number | null
  created_at: string
  updated_at: string
}

export interface SiteCheckResult {
  id: number
  monitor_id: number
  is_up: boolean
  status_code: number | null
  response_ms: number | null
  error: string | null
  checked_at: string | null
}

export interface SiteMonitorCreate {
  name: string
  target: string
  monitor_type?: string
  http_method?: string
  expected_status_codes?: string
  timeout?: number
  retries?: number
  check_interval?: number
  alert_enabled?: boolean
}

export function fetchSiteMonitors() {
  return api.get<SiteMonitor[]>('/site-monitors')
}

export function fetchSiteMonitor(id: number) {
  return api.get<SiteMonitor>(`/site-monitors/${id}`)
}

export function createSiteMonitor(data: SiteMonitorCreate) {
  return api.post<SiteMonitor>('/site-monitors', data)
}

export function updateSiteMonitor(id: number, data: Partial<SiteMonitorCreate>) {
  return api.put<SiteMonitor>(`/site-monitors/${id}`, data)
}

export function deleteSiteMonitor(id: number) {
  return api.delete(`/site-monitors/${id}`)
}

export function checkNow(id: number) {
  return api.post<SiteCheckResult>(`/site-monitors/${id}/check-now`)
}

export function fetchHistory(id: number, page = 1, pageSize = 20) {
  return api.get<{ items: SiteCheckResult[]; total: number; page: number; page_size: number }>(
    `/site-monitors/${id}/history`, { params: { page, page_size: pageSize } }
  )
}
