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
  group_name: string
  notification_group_id: number | null
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
  group_name?: string
  notification_group_id?: number | null
}

export function fetchSiteMonitors(group = '') {
  return api.get<SiteMonitor[]>('/site-monitors', { params: group ? { group } : {} })
}

export function fetchMonitorGroups() {
  return api.get<string[]>('/site-monitors/groups')
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

export interface SlaRow {
  name: string
  target: string
  monitor_type: string
  sla: number | null
  checks: number
  down_count: number
  period: string
}

export function fetchSlaSummary(period = 'monthly') {
  return api.get<SlaRow[]>('/site-monitors/sla-summary', { params: { period } })
}

export function exportSla(period = 'monthly') {
  return api.get('/site-monitors/export-sla', { params: { period }, responseType: 'blob' })
}

export interface HeatmapCell {
  time: string
  is_up: boolean
}

export function fetchHeatmap(id: number, days = 7) {
  return api.get<HeatmapCell[]>('/site-monitors/' + id + '/heatmap', { params: { days } })
}
