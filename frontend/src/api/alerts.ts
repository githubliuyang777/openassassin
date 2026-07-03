import { api } from './client'

export interface AlertItem {
  id: string
  source: string
  message: string
  severity: string
  link: string | null
}

export function fetchAlertSummary() {
  return api.get<AlertItem[]>('/alerts/summary')
}
