import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    get: mocks.get,
    post: mocks.post,
    put: mocks.put,
    delete: mocks.delete,
  },
}))

import {
  checkAllVulnerabilities,
  checkVulnerabilityComponent,
  createVulnerabilityComponent,
  deleteVulnerabilityComponent,
  fetchVulnerabilityCatalog,
  fetchVulnerabilityComponents,
  fetchVulnerabilityFindings,
  updateVulnerabilityComponent,
  updateVulnerabilityFindingStatus,
} from '@/api/vulnerabilities'

describe('vulnerability api', () => {
  it('calls the expected endpoints', () => {
    fetchVulnerabilityCatalog()
    expect(mocks.get).toHaveBeenCalledWith('/vulnerabilities/catalog')

    fetchVulnerabilityComponents()
    expect(mocks.get).toHaveBeenCalledWith('/vulnerabilities/components')

    createVulnerabilityComponent({ component_key: 'nginx', version: '1.24.0' })
    expect(mocks.post).toHaveBeenCalledWith('/vulnerabilities/components', {
      component_key: 'nginx',
      version: '1.24.0',
    })

    updateVulnerabilityComponent(1, { version: '1.24.1' })
    expect(mocks.put).toHaveBeenCalledWith('/vulnerabilities/components/1', { version: '1.24.1' })

    deleteVulnerabilityComponent(1)
    expect(mocks.delete).toHaveBeenCalledWith('/vulnerabilities/components/1')

    fetchVulnerabilityFindings(1)
    expect(mocks.get).toHaveBeenCalledWith('/vulnerabilities/components/1/findings')

    checkVulnerabilityComponent(1)
    expect(mocks.post).toHaveBeenCalledWith('/vulnerabilities/components/1/check')

    checkAllVulnerabilities()
    expect(mocks.post).toHaveBeenCalledWith('/vulnerabilities/check-all')

    updateVulnerabilityFindingStatus(2, 'ignored')
    expect(mocks.put).toHaveBeenCalledWith('/vulnerabilities/findings/2/status', { status: 'ignored' })
  })
})
