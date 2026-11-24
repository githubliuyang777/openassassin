import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  warning: vi.fn(),
  message: {
    warning: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
  },
}))

vi.mock('@/api/client', () => ({
  api: {
    post: vi.fn(),
  },
}))

vi.mock('naive-ui', async () => {
  const { defineComponent, h } = await vi.importActual<typeof import('vue')>('vue')

  return {
    NButton: defineComponent({
      name: 'NButton',
      props: {
        type: String,
        secondary: Boolean,
        size: String,
        disabled: Boolean,
        loading: Boolean,
      },
      emits: ['click'],
      setup(props, { slots, emit }) {
        return () => h('button', {
          disabled: props.disabled,
          onClick: () => emit('click'),
        }, slots.default?.())
      },
    }),
    useDialog: () => ({ warning: mocks.warning }),
    useMessage: () => mocks.message,
  }
})

import { api } from '@/api/client'
import BatchDeleteButton from '@/components/BatchDeleteButton.vue'
import { batchDeleteSiteMonitors } from '@/api/site-monitors'
import { batchDeleteDomains } from '@/api/domains'
import { batchDeleteWhoisDomains } from '@/api/domain-whois'
import { batchDeleteCredentials } from '@/api/credentials'
import { batchDeleteScripts } from '@/api/scripts'
import { batchDeleteHosts } from '@/api/hosts'
import { batchDeleteSubscriptions } from '@/api/subscriptions'
import { batchDeleteVulnerabilityComponents } from '@/api/vulnerabilities'
import { batchDeleteNotepads } from '@/api/notepads'
import { batchDeleteGroups, batchDeleteRecipients } from '@/api/notification-groups'
import { batchDeleteBaotaPanels } from '@/api/baota'

const cases = [
  ['site monitors', batchDeleteSiteMonitors, '/site-monitors/batch-delete'],
  ['domains', batchDeleteDomains, '/domains/batch-delete'],
  ['whois domains', batchDeleteWhoisDomains, '/whois-domains/batch-delete'],
  ['credentials', batchDeleteCredentials, '/credentials/batch-delete'],
  ['scripts', batchDeleteScripts, '/scripts/batch-delete'],
  ['hosts', batchDeleteHosts, '/hosts/batch-delete'],
  ['subscriptions', batchDeleteSubscriptions, '/subscriptions/batch-delete'],
  ['vulnerability components', batchDeleteVulnerabilityComponents, '/vulnerabilities/components/batch-delete'],
  ['notepads', batchDeleteNotepads, '/notepads/batch-delete'],
  ['notification groups', batchDeleteGroups, '/notification-groups/batch-delete'],
  ['notification recipients', batchDeleteRecipients, '/notification-recipients/batch-delete'],
  ['baota panels', batchDeleteBaotaPanels, '/baota/panels/batch-delete'],
] as const

beforeEach(() => {
  vi.clearAllMocks()
  ;(api.post as any).mockResolvedValue({ data: { deleted: 2, missing: [] } })
  mocks.warning.mockReturnValue(undefined)
})

describe('batch delete API', () => {
  it.each(cases)('%s uses the batch-delete endpoint', async (_name, action, path) => {
    const result = await (action as (ids: number[]) => Promise<any>)([1, 2])

    expect(api.post).toHaveBeenCalledWith(path, { ids: [1, 2] })
    expect(result.data).toEqual({ deleted: 2, missing: [] })
  })
})

describe('BatchDeleteButton', () => {
  it('asks for confirmation with the selected count and runs the action', async () => {
    const action = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(BatchDeleteButton, {
      props: { count: 2, noun: '站点监控', action },
    })

    await wrapper.find('button').trigger('click')

    expect(mocks.warning).toHaveBeenCalledTimes(1)
    const options = mocks.warning.mock.calls[0][0]
    expect(options.content).toContain('2')
    expect(options.content).toContain('站点监控')
    expect(options.content).toContain('不可恢复')

    await options.onPositiveClick()
    expect(action).toHaveBeenCalledTimes(1)
  })

  it('is disabled without a selection', () => {
    const wrapper = mount(BatchDeleteButton, {
      props: { count: 0, noun: '脚本', action: vi.fn() },
    })

    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })

  it('rejects selections above the backend limit', async () => {
    const wrapper = mount(BatchDeleteButton, {
      props: { count: 501, noun: '脚本', action: vi.fn() },
    })

    await wrapper.find('button').trigger('click')

    expect(mocks.message.warning).toHaveBeenCalled()
    expect(mocks.warning).not.toHaveBeenCalled()
  })
})
