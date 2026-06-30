import { api } from './client'

export interface Script {
  id: number
  name: string
  description: string
  type: string
  content: string
  timeout: number
  env_vars: Record<string, string>
  created_at: string
  updated_at: string
}

export function fetchScripts(page = 1, pageSize = 20, search = '') {
  return api.get('/scripts', { params: { page, page_size: pageSize, search } })
}

export function fetchScript(id: number) {
  return api.get(`/scripts/${id}`)
}

export function createScript(data: Partial<Script>) {
  return api.post('/scripts', data)
}

export function updateScript(id: number, data: Partial<Script>) {
  return api.put(`/scripts/${id}`, data)
}

export function deleteScript(id: number) {
  return api.delete(`/scripts/${id}`)
}

export function executeScript(id: number, credentialIds: number[] = []) {
  return api.post(`/scripts/${id}/execute`, { credential_ids: credentialIds })
}
