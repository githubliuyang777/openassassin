import { api } from './client'

export interface BaotaPanel {
  id: number
  name: string
  panel_url: string
  verify_tls: boolean
  enabled: boolean
  api_key_configured: boolean
  created_at: string
  updated_at: string
}

export interface BaotaPanelCreate {
  name: string
  panel_url: string
  api_key: string
  verify_tls?: boolean
  enabled?: boolean
}

export interface BaotaPanelUpdate {
  name?: string
  panel_url?: string
  api_key?: string
  verify_tls?: boolean
  enabled?: boolean
}

export interface BaotaSite {
  id: number
  name: string
}

export interface BaotaDockerSite {
  id: number
  name: string
  type: string
  project_name: string
}

export interface BaotaOrder {
  index: string
  domains: string[]
  status: string
  cert_timeout: number
  auth_type: string
}

export interface BaotaTestResult {
  ok: boolean
  message: string
  sites: BaotaSite[]
  orders: BaotaOrder[]
}

export function fetchBaotaPanels() {
  return api.get<BaotaPanel[]>('/baota/panels')
}

export function createBaotaPanel(data: BaotaPanelCreate) {
  return api.post<BaotaPanel>('/baota/panels', data)
}

export function updateBaotaPanel(id: number, data: BaotaPanelUpdate) {
  return api.put<BaotaPanel>(`/baota/panels/${id}`, data)
}

export function deleteBaotaPanel(id: number) {
  return api.delete(`/baota/panels/${id}`)
}

export function testBaotaPanel(id: number) {
  return api.post<BaotaTestResult>(`/baota/panels/${id}/test`)
}

export function fetchBaotaDockerSites(panelId: number) {
  // 后端宝塔请求超时为 90s，前端留出余量，避免提前超时后重复发起请求
  return api.get<BaotaDockerSite[]>(`/baota/panels/${panelId}/docker-sites`, { timeout: 95000 })
}
