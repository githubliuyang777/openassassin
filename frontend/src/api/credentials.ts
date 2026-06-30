import { api } from './client'

export interface Credential {
  id: number
  name: string
  key: string
  description: string
  created_at: string
  updated_at: string
}

export interface CredentialReveal extends Credential {
  value: string
}

export function fetchCredentials() {
  return api.get<Credential[]>('/credentials')
}

export function createCredential(data: { name: string; key: string; value: string; description: string }) {
  return api.post('/credentials', data)
}

export function revealCredential(id: number) {
  return api.get<CredentialReveal>(`/credentials/${id}`)
}

export function deleteCredential(id: number) {
  return api.delete(`/credentials/${id}`)
}
