import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  dialog: { warning: vi.fn() },
  fetchWhoisDomains: vi.fn(),
  batchDeleteWhoisDomains: vi.fn(),
  fetchGroups: vi.fn(),
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
    NH3: slotComponent('h3'),
    NSwitch: slotComponent('span'),
    NSelect: slotComponent('select'),
    NDivider: slotComponent('span'),
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

vi.mock('@/api/domain-whois', () => ({
  fetchWhoisDomains: mocks.fetchWhoisDomains,
  batchDeleteWhoisDomains: mocks.batchDeleteWhoisDomains,
  addWhoisDomain: vi.fn(),
  batchImportWhoisDomains: vi.fn(),
  refreshAllWhoisDomains: vi.fn(),
  refreshWhoisDomain: vi.fn(),
  deleteWhoisDomain: vi.fn(),
  toggleWhoisDomainAlert: vi.fn(),
  batchToggleWhoisDomainAlert: vi.fn(),
  batchSetWhoisNotificationGroup: vi.fn(),
}))

vi.mock('@/api/notification-groups', () => ({
  fetchGroups: mocks.fetchGroups,
}))

import DomainWhoisView from '@/views/DomainWhoisView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.fetchWhoisDomains.mockResolvedValue({
    data: [{ id: 11, domain: 'one.example.com' }, { id: 12, domain: 'two.example.com' }],
  })
  mocks.fetchGroups.mockResolvedValue({ data: [] })
  mocks.batchDeleteWhoisDomains.mockResolvedValue({ data: { deleted: 2, missing: [] } })
})

describe('DomainWhoisView batch delete', () => {
  it('deletes selected WHOIS domains after confirmation', async () => {
    const wrapper = mount(DomainWhoisView)
    await flushPromises()

    const button = wrapper.findAll('button').find(item => item.text().includes('批量删除'))
    expect(button).toBeDefined()
    await button!.trigger('click')

    const options = mocks.dialog.warning.mock.calls[0][0]
    expect(options.content).toContain('2')
    await options.onPositiveClick()
    await flushPromises()

    expect(mocks.batchDeleteWhoisDomains).toHaveBeenCalledWith([11, 12])
    expect(mocks.message.success).toHaveBeenCalledWith('已删除 2 个 WHOIS 域名')
  })
})
