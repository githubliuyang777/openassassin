import { api } from './client'

export interface Subscription {
  id: number
  name: string
  repo_url: string
  repo_platform: string
  repo_owner: string
  repo_name: string
  last_version: string
  last_checked_at: string | null
  alert_count: number
  alert_enabled: boolean
  notification_group_id: number | null
  created_at: string
  updated_at: string
}

export interface SubscriptionCreate {
  name: string
  repo_url: string
  repo_platform: string
  repo_owner: string
  repo_name: string
  alert_enabled?: boolean
  notification_group_id?: number | null
}

export interface SubscriptionAlert {
  id: number
  subscription_id: number
  alert_type: string
  title: string
  summary: string
  url: string
  occurred_at: string | null
  is_read: boolean
  created_at: string
}

export interface RepoLookupResult {
  repo_owner: string
  repo_name: string
  repo_platform: string
  description: string
  latest_version: string
}

export function fetchSubscriptions() {
  return api.get<Subscription[]>('/subscriptions')
}

export function createSubscription(data: SubscriptionCreate) {
  return api.post<Subscription>('/subscriptions', data)
}

export function updateSubscription(id: number, data: Partial<SubscriptionCreate>) {
  return api.put<Subscription>(`/subscriptions/${id}`, data)
}

export function deleteSubscription(id: number) {
  return api.delete(`/subscriptions/${id}`)
}

export function fetchAlerts(subId: number) {
  return api.get<SubscriptionAlert[]>(`/subscriptions/${subId}/alerts`)
}

export function markAlertRead(alertId: number) {
  return api.put(`/subscriptions/alerts/${alertId}/read`)
}

export function lookupRepo(repoUrl: string) {
  return api.post<RepoLookupResult>('/subscriptions/lookup', { repo_url: repoUrl })
}
