import { api } from './client'

export interface Host {
  id: number
  name: string
  hostname: string
  port: number
  username: string
  credential_id: number | null
  aws_instance_id: string | null
  aws_region: string | null
  aws_credential_id: number | null
  description: string
  agent_version: string
  last_seen_at: string | null
  is_online: boolean
  cpu_usage: number
  cpu_count: number
  mem_usage: number
  disk_usage: number
  alert_enabled: boolean
  notification_group_id: number | null
  created_at: string
  updated_at: string
}

export interface HostCreate {
  name: string
  hostname: string
  port: number
  username: string
  credential_id: number | null
  aws_instance_id: string | null
  aws_region: string | null
  aws_credential_id: number | null
  description: string
}

export interface HostUpdate {
  name?: string
  hostname?: string
  port?: number
  username?: string
  credential_id?: number | null
  aws_instance_id?: string | null
  aws_region?: string | null
  aws_credential_id?: number | null
  description?: string
  alert_enabled?: boolean
  notification_group_id?: number | null
}

export interface HostImportRequest {
  aws_credential_id: number
  aws_region: string
  aws_instance_id: string
  name?: string
  username?: string
  port?: number
  credential_id?: number | null
  description?: string
}

export interface HostMetric {
  collected_at: string | null
  cpu_percent: number
  mem_percent: number
  disk_percent: number
  load_1m: number
}

export interface LatestMetric {
  id: number; host_id: number; cpu_percent: number; cpu_count: number
  mem_total_mb: number; mem_used_mb: number; mem_percent: number
  disk_total_gb: number; disk_used_gb: number; disk_percent: number
  load_1m: number; load_5m: number; load_15m: number
  net_rx_bytes: number; net_tx_bytes: number
  process_count: number; uptime_seconds: number; collected_at: string | null
}

export interface HostEvent {
  id: number
  host_id: number
  category: string
  severity: string
  source: string
  title: string
  detail: string
  labels: string
  created_at: string | null
}

export function fetchHosts() { return api.get<Host[]>('/hosts') }
export function fetchHost(id: number) { return api.get<Host>(`/hosts/${id}`) }
export function createHost(data: HostCreate) { return api.post<Host>('/hosts', data) }
export function importFromEc2(data: HostImportRequest) { return api.post<Host>('/hosts/import', data) }
export function updateHost(id: number, data: HostUpdate) { return api.put<Host>(`/hosts/${id}`, data) }
export function deleteHost(id: number) { return api.delete(`/hosts/${id}`) }
export function fetchHostMetrics(id: number, hours = 24) { return api.get<{ items: HostMetric[] }>(`/hosts/${id}/metrics`, { params: { hours } }) }
export function fetchLatestMetrics(id: number) { return api.get<LatestMetric>(`/hosts/${id}/metrics/latest`) }
export function fetchAgentToken(id: number) { return api.get<{ agent_token: string }>(`/hosts/${id}/agent-token`) }
export function regenerateAgentToken(id: number) { return api.post<{ agent_token: string }>(`/hosts/${id}/regenerate-token`) }
export function fetchHostEvents(id: number, hours = 24, severity?: string, category?: string) {
  const params: Record<string, string | number> = { hours }
  if (severity) params.severity = severity
  if (category) params.category = category
  return api.get<{ items: HostEvent[] }>(`/hosts/${id}/events`, { params })
}
