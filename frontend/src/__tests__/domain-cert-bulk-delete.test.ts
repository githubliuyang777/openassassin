import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  dialog: { warning: vi.fn() },
  fetchDomains: vi.fn(),
  batchDeleteDomains: vi.fn(),
  fetchGroups: vi.fn(),
  fetchBaotaPanels: vi.fn(),
  fetchCertProviders: vi.fn(),
  auth: { user: { role: 'viewer' }, fetchMe: vi.fn() },
}))

vi.mock('naive-ui', async () => {
  const { defineComponent, h, watch } = await vi.importActual<typeof import('vue')>('vue')
  const slotComponent = (tag: string) => defineComponent({
    name: tag,
    setup(_, { slots, attrs }) {
      return () => h(tag, attrs, slots.default ? slots.default() : undefined)
    },
  })

  return {
    NButton: slotComponent('button'),
    NIcon: slotComponent('span'),
    NSpace: slotComponent('div'),
    NModal: slotComponent('div'),
    NForm: slotComponent('form'),
    NFormItem: slotComponent('div'),
    NInput: slotComponent('input'),
    NInputNumber: slotComponent('input'),
    NH3: slotComponent('h3'),
    NSwitch: slotComponent('span'),
    NSelect: slotComponent('select'),
    NDivider: slotComponent('span'),
    NEllipsis: slotComponent('span'),
    NTag: slotComponent('span'),
    NDataTable: defineComponent({
      name: 'NDataTable',
      props: { data: { type: Array, default: () => [] } },
      emits: ['update:checked-row-keys'],
      setup(props, { emit }) {
        watch(() => props.data, (data: any[]) => {
          if (data.length) emit('update:checked-row-keys', data.map(row => row.id))
        }, { immediate: true })
        return () => h('div', 'data-table')
      },
    }),
    useMessage: () => mocks.message,
    useDialog: () => mocks.dialog,
  }
})

vi.mock('@/api/domains', () => ({
  fetchDomains: mocks.fetchDomains,
  batchDeleteDomains: mocks.batchDeleteDomains,
  addDomain: vi.fn(),
  batchImportDomains: vi.fn(),
  refreshAllDomains: vi.fn(),
  refreshDomain: vi.fn(),
  deleteDomain: vi.fn(),
  toggleDomainAlert: vi.fn(),
  batchToggleDomainAlert: vi.fn(),
  batchSetNotificationGroup: vi.fn(),
  updateDomain: vi.fn(),
  renewDomainCert: vi.fn(),
}))

vi.mock('@/api/notification-groups', () => ({
  fetchGroups: mocks.fetchGroups,
}))

vi.mock('@/api/baota', () => ({
  fetchBaotaPanels: mocks.fetchBaotaPanels,
  createBaotaPanel: vi.fn(),
  updateBaotaPanel: vi.fn(),
  deleteBaotaPanel: vi.fn(),
  testBaotaPanel: vi.fn(),
  fetchBaotaDockerSites: vi.fn(),
  batchDeleteBaotaPanels: vi.fn(),
}))

vi.mock('@/api/cert-providers', () => ({
  fetchCertProviders: mocks.fetchCertProviders,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mocks.auth,
}))

import DomainCertView from '@/views/DomainCertView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.fetchDomains.mockResolvedValue({
    data: [{ id: 21, domain: 'one.example.com', port: 443 }, { id: 22, domain: 'two.example.com', port: 443 }],
  })
  mocks.fetchGroups.mockResolvedValue({ data: [] })
  mocks.fetchBaotaPanels.mockResolvedValue({ data: [] })
  mocks.fetchCertProviders.mockResolvedValue({ data: [] })
  mocks.batchDeleteDomains.mockResolvedValue({ data: { deleted: 2, missing: [] } })
})

describe('DomainCertView batch delete', () => {
  it('deletes selected domains after confirmation', async () => {
    const wrapper = mount(DomainCertView)
    await flushPromises()

    const button = wrapper.findAll('button').find(item => item.text().includes('批量删除'))
    expect(button).toBeDefined()
    await button!.trigger('click')

    const options = mocks.dialog.warning.mock.calls[0][0]
    expect(options.content).toContain('2')
    await options.onPositiveClick()
    await flushPromises()

    expect(mocks.batchDeleteDomains).toHaveBeenCalledWith([21, 22])
    expect(mocks.message.success).toHaveBeenCalledWith('已删除 2 个域名')
  })
})
