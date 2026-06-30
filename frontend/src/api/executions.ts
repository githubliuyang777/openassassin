import { api } from './client'

export interface Execution {
  id: number
  script_id: number
  status: string
  started_at: string
  finished_at: string | null
  exit_code: number | null
  triggered_by: string
  credential_ids: number[]
}

export function fetchExecutions(page = 1, pageSize = 20, scriptId?: number) {
  return api.get('/executions', {
    params: { page, page_size: pageSize, script_id: scriptId },
  })
}

export function fetchExecution(id: number) {
  return api.get(`/executions/${id}`)
}

export function fetchExecutionLog(id: number, tail = 0) {
  return api.get(`/executions/${id}/log`, { params: { tail } })
}
