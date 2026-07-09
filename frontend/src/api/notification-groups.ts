import { api } from './client'

export interface NotificationRecipient {
  id: number
  name: string
  channel_type: string
  address: string
  group_id: number
  created_at: string
}

export interface NotificationGroup {
  id: number
  name: string
  recipients: NotificationRecipient[]
  created_at: string
  updated_at: string
}

export interface NotificationGroupCreate { name: string }
export interface NotificationRecipientCreate {
  name: string
  channel_type: string
  address: string
  group_id: number
}

export function fetchGroups() {
  return api.get<NotificationGroup[]>('/notification-groups')
}

export function createGroup(data: NotificationGroupCreate) {
  return api.post<NotificationGroup>('/notification-groups', data)
}

export function updateGroup(id: number, data: Partial<NotificationGroupCreate>) {
  return api.put<NotificationGroup>(`/notification-groups/${id}`, data)
}

export function deleteGroup(id: number) {
  return api.delete(`/notification-groups/${id}`)
}

export function fetchRecipients() {
  return api.get<NotificationRecipient[]>('/notification-recipients')
}

export function createRecipient(data: NotificationRecipientCreate) {
  return api.post<NotificationRecipient>('/notification-recipients', data)
}

export function updateRecipient(id: number, data: Partial<NotificationRecipientCreate>) {
  return api.put<NotificationRecipient>(`/notification-recipients/${id}`, data)
}

export function deleteRecipient(id: number) {
  return api.delete(`/notification-recipients/${id}`)
}
