import { api } from './client'

export interface DingTalkConfig {
  id: number
  webhook_url: string
  is_enabled: boolean
  secret_configured: boolean
  created_at: string
  updated_at: string
}

export interface DingTalkStatus {
  configured: boolean
  enabled: boolean
  webhook_masked: string | null
}

export function getDingTalkConfig() {
  return api.get<DingTalkConfig>('/dingtalk/config').then(r => r.data)
}

export function updateDingTalkConfig(data: { webhook_url?: string; secret?: string; is_enabled?: boolean }) {
  return api.put<DingTalkConfig>('/dingtalk/config', data).then(r => r.data)
}

export function getDingTalkStatus() {
  return api.get<DingTalkStatus>('/dingtalk/status').then(r => r.data)
}

export function testDingTalk() {
  return api.post<{ message: string }>('/dingtalk/test').then(r => r.data)
}
