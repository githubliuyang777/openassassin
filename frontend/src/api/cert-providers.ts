import { api } from './client'

export interface CertProvider {
  key: string
  name: string
  enabled: boolean
}

export function fetchCertProviders() {
  return api.get<CertProvider[]>('/cert-providers')
}
