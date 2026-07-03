import { api } from './client'

export interface AuditLogEntry {
  id: number
  user_id: number
  username: string
  action: string
  resource: string
  resource_type: string
  detail: string
  ip_address: string
  ip_location: string
  user_agent: string
  status_code: number
  created_at: string
}

export interface AuditLogListResponse {
  items: AuditLogEntry[]
  total: number
  page: number
  page_size: number
}

export function fetchAuditLogs(params: {
  page?: number
  page_size?: number
  username?: string
  action?: string
  resource?: string
  date_from?: string
  date_to?: string
}) {
  return api.get<AuditLogListResponse>('/audit-logs', { params })
}
