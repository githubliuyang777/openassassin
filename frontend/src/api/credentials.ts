import { api } from './client'

export interface Credential {
  id: number
  name: string
  key: string
  description: string
  type: string
  expires_at: string | null
  alert_enabled: boolean
  notification_group_id: number | null
  created_at: string
  updated_at: string
}

export interface CredentialReveal extends Credential {
  value: string
}

export function fetchCredentials() {
  return api.get<Credential[]>('/credentials')
}

export function createCredential(data: {
  name: string; key: string; value: string; description: string
  type?: string; expires_at?: string | null; alert_enabled?: boolean
  notification_group_id?: number | null
}) {
  return api.post('/credentials', data)
}

export function revealCredential(id: number) {
  return api.get<CredentialReveal>(`/credentials/${id}`)
}

export function parseKubeconfig(value: string) {
  return api.post<{ expires_at: string; days_left: number }>('/credentials/parse-kubeconfig', { value })
}

export function updateCredential(id: number, data: {
  description?: string; type?: string; expires_at?: string | null; alert_enabled?: boolean
  notification_group_id?: number | null
}) {
  return api.put<Credential>(`/credentials/${id}`, data)
}

export function toggleCredentialAlert(id: number, alertEnabled: boolean) {
  return api.put<Credential>(`/credentials/${id}`, { alert_enabled: alertEnabled })
}

export function deleteCredential(id: number) {
  return api.delete(`/credentials/${id}`)
}

export const CREDENTIAL_TYPES = [
  { label: '通用密钥', value: 'generic' },
  { label: 'Kubeconfig', value: 'kubeconfig' },
  { label: 'TLS 证书', value: 'tls_cert' },
  { label: 'API Token', value: 'api_token' },
  { label: 'SSH 密码', value: 'ssh_password' },
  { label: 'SSH 私钥', value: 'ssh_key' },
  { label: 'AWS', value: 'aws' },
] as const

export function getTypeLabel(type: string): string {
  return CREDENTIAL_TYPES.find(t => t.value === type)?.label || type
}
