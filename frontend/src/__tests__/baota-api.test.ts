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
  createBaotaPanel,
  deleteBaotaPanel,
  fetchBaotaPanels,
  testBaotaPanel,
  updateBaotaPanel,
} from '@/api/baota'
import { fetchCertProviders } from '@/api/cert-providers'
import { renewDomainCert, updateDomain } from '@/api/domains'

describe('certificate provider api', () => {
  it('calls the expected endpoints', () => {
    fetchCertProviders()
    expect(mocks.get).toHaveBeenCalledWith('/cert-providers')

    fetchBaotaPanels()
    expect(mocks.get).toHaveBeenCalledWith('/baota/panels')

    createBaotaPanel({
      name: 'panel',
      panel_url: 'https://panel.example.com:8888',
      api_key: 'secret',
    })
    expect(mocks.post).toHaveBeenCalledWith('/baota/panels', {
      name: 'panel',
      panel_url: 'https://panel.example.com:8888',
      api_key: 'secret',
    })

    updateBaotaPanel(1, { name: 'renamed' })
    expect(mocks.put).toHaveBeenCalledWith('/baota/panels/1', { name: 'renamed' })

    testBaotaPanel(1)
    expect(mocks.post).toHaveBeenCalledWith('/baota/panels/1/test')

    deleteBaotaPanel(1)
    expect(mocks.delete).toHaveBeenCalledWith('/baota/panels/1')

    updateDomain(2, {
      cert_provider: 'baota',
      cert_provider_config: { panel_id: 1, site_name: 'example.com' },
      cert_auto_renew: true,
    })
    expect(mocks.put).toHaveBeenCalledWith('/domains/2', {
      cert_provider: 'baota',
      cert_provider_config: { panel_id: 1, site_name: 'example.com' },
      cert_auto_renew: true,
    })

    renewDomainCert(2)
    expect(mocks.post).toHaveBeenCalledWith('/domains/2/renew-cert')
  })
})
