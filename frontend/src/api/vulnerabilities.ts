import { api } from './client'

export interface VulnerabilityCatalogItem {
  key: string
  name: string
  category: string
  source: string
  needs_package: boolean
}

export interface SeverityCounts {
  critical: number
  high: number
  medium: number
  low: number
  unknown: number
}

export interface VulnerabilityComponent {
  id: number
  name: string
  component_key: string
  version: string
  package_name: string
  alert_enabled: boolean
  last_checked_at: string | null
  last_check_error: string
  severity_counts: SeverityCounts
  open_count: number
  created_at: string
  updated_at: string
}

export interface VulnerabilityFinding {
  id: number
  component_id: number
  vuln_id: string
  title: string
  severity: string
  cvss_score: number | null
  fixed_version: string
  url: string
  source: string
  published_at: string | null
  first_seen_at: string
  status: string
}

export interface VulnerabilityComponentCreate {
  component_key: string
  version: string
  package_name?: string
  alert_enabled?: boolean
}

export interface VulnerabilityComponentUpdate {
  version?: string
  package_name?: string
  alert_enabled?: boolean
}

export function fetchVulnerabilityCatalog() {
  return api.get<VulnerabilityCatalogItem[]>('/vulnerabilities/catalog')
}

export function fetchVulnerabilityComponents() {
  return api.get<VulnerabilityComponent[]>('/vulnerabilities/components')
}

export function createVulnerabilityComponent(data: VulnerabilityComponentCreate) {
  return api.post<VulnerabilityComponent>('/vulnerabilities/components', data)
}

export function updateVulnerabilityComponent(id: number, data: VulnerabilityComponentUpdate) {
  return api.put<VulnerabilityComponent>(`/vulnerabilities/components/${id}`, data)
}

export function deleteVulnerabilityComponent(id: number) {
  return api.delete(`/vulnerabilities/components/${id}`)
}

export function fetchVulnerabilityFindings(componentId: number) {
  return api.get<VulnerabilityFinding[]>(`/vulnerabilities/components/${componentId}/findings`)
}

export function checkVulnerabilityComponent(id: number) {
  return api.post(`/vulnerabilities/components/${id}/check`)
}

export function checkAllVulnerabilities() {
  return api.post('/vulnerabilities/check-all')
}

export function updateVulnerabilityFindingStatus(id: number, status: 'open' | 'ignored') {
  return api.put(`/vulnerabilities/findings/${id}/status`, { status })
}
