import { api } from './client'

export interface HostAgentStatus {
  id: number
  name: string
  hostname: string
  is_online: boolean
  last_seen_at: string | null
  cpu_usage: number
  mem_usage: number
  disk_usage: number
  agent_version: string
}

export function fetchAgentStatus() {
  return api.get<HostAgentStatus[]>('/agents/status')
}
