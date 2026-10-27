import { api } from './client'

export interface VersionInfo {
  version: string
}

export function fetchVersion(): Promise<VersionInfo> {
  return api.get<VersionInfo>('/system/version').then((r) => r.data)
}
