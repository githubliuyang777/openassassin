import { api } from './client'

export interface NetworkTestRequest {
  host: string
  port: number
  timeout: number
}

export interface NetworkTestResult {
  success: boolean
  host: string
  port: number
  latency_ms: number | null
  error: string | null
}

export function testNetwork(data: NetworkTestRequest) {
  return api.post<NetworkTestResult>('/network/test', data)
}
