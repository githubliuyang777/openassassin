import { api } from './client'

export interface Host {
  id: number
  name: string
  hostname: string
  port: number
  username: string
  credential_id: number | null
  description: string
  created_at: string
  updated_at: string
}

export interface HostCreate {
  name: string
  hostname: string
  port: number
  username: string
  credential_id: number | null
  description: string
}

export function fetchHosts() {
  return api.get<Host[]>('/hosts')
}

export function fetchHost(id: number) {
  return api.get<Host>(`/hosts/${id}`)
}

export function createHost(data: HostCreate) {
  return api.post<Host>('/hosts', data)
}

export function updateHost(id: number, data: Partial<HostCreate>) {
  return api.put<Host>(`/hosts/${id}`, data)
}

export function deleteHost(id: number) {
  return api.delete(`/hosts/${id}`)
}
