import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  dialog: { warning: vi.fn() },
  fetchSiteMonitors: vi.fn(),
  fetchMonitorGroups: vi.fn(),
  batchDeleteSiteMonitors: vi.fn(),
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
    NText: slotComponent('span'),
    NSpace: slotComponent('div'),
    NModal: slotComponent('div'),
    NForm: slotComponent('form'),
    NFormItem: slotComponent('div'),
    NInput: slotComponent('input'),
    NInputNumber: slotComponent('input'),
    NSelect: slotComponent('select'),
    NSwitch: slotComponent('span'),
    NH3: slotComponent('h3'),
    NGrid: slotComponent('div'),
    NGridItem: slotComponent('div'),
    NDrawer: slotComponent('div'),
    NDrawerContent: slotComponent('div'),
    NTable: slotComponent('table'),
    NPagination: slotComponent('div'),
    NDropdown: slotComponent('div'),
    NRadioGroup: slotComponent('div'),
    NRadioButton: slotComponent('button'),
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

vi.mock('@/api/site-monitors', () => ({
  fetchSiteMonitors: mocks.fetchSiteMonitors,
  fetchMonitorGroups: mocks.fetchMonitorGroups,
  batchDeleteSiteMonitors: mocks.batchDeleteSiteMonitors,
  createSiteMonitor: vi.fn(),
  updateSiteMonitor: vi.fn(),
  deleteSiteMonitor: vi.fn(),
  checkNow: vi.fn(),
  fetchHistory: vi.fn(),
  exportSla: vi.fn(),
  fetchHeatmap: vi.fn(),
  batchToggleAlert: vi.fn(),
  batchSetNotificationGroup: vi.fn(),
}))

vi.mock('@/api/notification-groups', () => ({
  fetchGroups: mocks.fetchGroups,
}))

import SiteMonitorView from '@/views/SiteMonitorView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.fetchSiteMonitors.mockResolvedValue({
    data: [
      { id: 1, name: 'one', target: 'https://one.example.com' },
      { id: 2, name: 'two', target: 'https://two.example.com' },
    ],
  })
  mocks.fetchMonitorGroups.mockResolvedValue({ data: [] })
  mocks.fetchGroups.mockResolvedValue({ data: [] })
  mocks.batchDeleteSiteMonitors.mockResolvedValue({ data: { deleted: 2, missing: [] } })
})

describe('SiteMonitorView batch delete', () => {
  it('deletes the selected monitors after confirmation', async () => {
    const wrapper = mount(SiteMonitorView)
    await flushPromises()

    const button = wrapper.findAll('button').find(item => item.text().includes('批量删除'))
    expect(button).toBeDefined()
    await button!.trigger('click')

    expect(mocks.dialog.warning).toHaveBeenCalledTimes(1)
    const options = mocks.dialog.warning.mock.calls[0][0]
    expect(options.content).toContain('2')

    await options.onPositiveClick()
    await flushPromises()

    expect(mocks.batchDeleteSiteMonitors).toHaveBeenCalledWith([1, 2])
    expect(mocks.message.success).toHaveBeenCalledWith('已删除 2 个站点监控')
  })
})
