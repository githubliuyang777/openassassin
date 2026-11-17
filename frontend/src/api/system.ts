import { api } from './client'

export interface VersionInfo {
  version: string
}

export interface TracingInfo {
  enabled: boolean
  ui_url: string
}

export function fetchVersion(): Promise<VersionInfo> {
  return api.get<VersionInfo>('/system/version').then((r) => r.data)
}

export function fetchTracingInfo(): Promise<TracingInfo> {
  return api.get<TracingInfo>('/system/tracing').then((r) => r.data)
}

export function buildTraceUrl(uiUrl: string, traceId: string): string {
  if (!/^https?:\/\//.test(uiUrl)) return ''
  if (!/^[0-9a-f]{32}$/i.test(traceId)) return ''
  return `${uiUrl.replace(/\/+$/, '')}/trace/${traceId}`
}
