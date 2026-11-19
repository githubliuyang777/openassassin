import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  fetchAuditLogs: vi.fn(),
  fetchTracingInfo: vi.fn(),
}))

vi.mock('naive-ui', async () => {
  const { defineComponent, h } = await vi.importActual<typeof import('vue')>('vue')

  const slotComponent = (name: string) => defineComponent({
    name,
    setup(_, { slots, attrs }) {
      return () => h('div', attrs, slots.default?.())
    },
  })

  const NDataTable = defineComponent({
    name: 'NDataTable',
    props: {
      remote: Boolean,
      pagination: Object,
      data: Array,
      columns: Array,
      loading: Boolean,
    },
    emits: ['update:page', 'update:page-size'],
    setup() {
      return () => h('div', { class: 'n-data-table-stub' })
    },
  })

  return {
    NH3: slotComponent('NH3'),
    NSpace: slotComponent('NSpace'),
    NFormItem: defineComponent({
      name: 'NFormItem',
      props: { label: String },
      setup(_, { slots }) {
        return () => h('div', slots.default?.())
      },
    }),
    NInput: defineComponent({
      name: 'NInput',
      props: { value: [String, Number] },
      emits: ['update:value'],
      setup(props) {
        return () => h('input', { value: props.value })
      },
    }),
    NSelect: slotComponent('NSelect'),
    NDatePicker: slotComponent('NDatePicker'),
    NButton: slotComponent('NButton'),
    NTag: slotComponent('NTag'),
    NDataTable,
    useMessage: () => mocks.message,
  }
})

vi.mock('@/api/audit-logs', () => ({
  fetchAuditLogs: mocks.fetchAuditLogs,
}))

vi.mock('@/api/system', () => ({
  fetchTracingInfo: mocks.fetchTracingInfo,
  buildTraceUrl: () => '',
}))

import AuditLogView from '@/views/AuditLogView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.fetchTracingInfo.mockResolvedValue({ enabled: false, ui_url: '' })
  mocks.fetchAuditLogs.mockImplementation((params: { page: number; page_size: number }) =>
    Promise.resolve({
      data: {
        items: [],
        total: 120,
        page: params.page,
        page_size: params.page_size,
      },
    }),
  )
})

describe('AuditLogView pagination', () => {
  it('uses remote pagination and reloads on page/page-size changes', async () => {
    const wrapper = mount(AuditLogView)
    await flushPromises()

    const table = wrapper.findComponent({ name: 'NDataTable' })
    expect(table.exists()).toBe(true)
    expect(table.props('remote')).toBe(true)
    expect(table.props('pagination')).toMatchObject({
      page: 1,
      pageSize: 50,
      itemCount: 120,
    })
    expect(mocks.fetchAuditLogs).toHaveBeenLastCalledWith({ page: 1, page_size: 50 })

    table.vm.$emit('update:page', 2)
    await flushPromises()
    expect(mocks.fetchAuditLogs).toHaveBeenLastCalledWith({ page: 2, page_size: 50 })

    table.vm.$emit('update:page-size', 100)
    await flushPromises()
    expect(mocks.fetchAuditLogs).toHaveBeenLastCalledWith({ page: 1, page_size: 100 })
  })
})
