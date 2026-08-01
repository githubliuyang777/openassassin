import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'

const { push } = vi.hoisted(() => ({ push: vi.fn() }))
const { messages } = vi.hoisted(() => ({ messages: [] as Array<{ success: any; error: any; warning: any }> }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('@/api/scripts', () => ({
  fetchScripts: vi.fn(),
  deleteScript: vi.fn(),
}))

vi.mock('naive-ui', async () => {
  const vue = await vi.importActual<typeof import('vue')>('vue')
  const { defineComponent: def, h: hh } = vue

  // 通用槽位包装组件：渲染默认插槽文本
  const Slot = (name: string) =>
    def({
      name,
      setup(_: unknown, { slots }: any) {
        return () => hh('div', { class: `n-${name.toLowerCase()}` }, slots.default?.())
      },
    })

  const NButton = def({
    name: 'NButton',
    setup(_: unknown, { slots }: any) {
      return () => hh('button', { class: 'n-button' }, slots.default?.())
    },
  })

  const NInput = def({
    name: 'NInput',
    props: ['modelValue'],
    emits: ['update:value'],
    setup(props: any, { emit }: any) {
      return () => hh('input', {
        class: 'n-input',
        value: props.modelValue ?? '',
        onInput: (e: Event) => emit('update:value', (e.target as HTMLInputElement).value),
      })
    },
  })

  const NDataTable = def({
    name: 'NDataTable',
    props: ['data', 'columns', 'loading'],
    setup(props: any) {
      return () =>
        hh('div', { class: 'n-data-table' }, (props.data || []).map((row: any) =>
          hh('div', { class: 'data-table-row', key: row.id },
            (props.columns || []).map((col: any) =>
              hh('div', { class: `cell cell-${col.key}` },
                col.render ? col.render(row) : String(row[col.key] ?? ''),
              ),
            ),
          ),
        ))
    },
  })

  const NModal = def({
    name: 'NModal',
    props: ['show', 'title'],
    setup(props: any, { slots }: any) {
      return () => {
        if (!props.show) return null
        return hh('div', { class: 'n-modal' }, [
          props.title ? hh('div', { class: 'n-modal-title' }, props.title) : null,
          slots.default?.(),
          slots.footer?.(),
        ])
      }
    },
  })

  return {
    NH3: Slot('NH3'),
    NSpace: Slot('NSpace'),
    NIcon: Slot('NIcon'),
    NTag: Slot('NTag'),
    NButton,
    NInput,
    NDataTable,
    NModal,
    useMessage: () => {
      const m = { success: vi.fn(), error: vi.fn(), warning: vi.fn() }
      messages.push(m)
      return m
    },
  }
})

import ScriptListView from '@/views/ScriptListView.vue'
import { fetchScripts, deleteScript } from '@/api/scripts'

const SCRIPT_ROWS = [
  {
    id: 1, name: 'deploy.sh', description: '发布部署', type: 'shell', content: 'echo hi', timeout: 30,
    env_vars: {}, created_at: '2026-07-01T00:00:00', updated_at: '2026-07-02T00:00:00',
  },
  {
    id: 2, name: 'backup.py', description: '', type: 'python', content: 'print(1)', timeout: 60,
    env_vars: {}, created_at: '2026-07-01T00:00:00', updated_at: '2026-07-01T00:00:00',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  messages.length = 0
  vi.mocked(fetchScripts).mockResolvedValue({ data: { items: SCRIPT_ROWS, total: 2 } } as any)
  vi.mocked(deleteScript).mockResolvedValue({} as any)
})

describe('ScriptListView', () => {
  it('renders scripts from API on mount', async () => {
    const wrapper = mount(ScriptListView)
    await flushPromises()

    expect(fetchScripts).toHaveBeenCalledWith(1, 20, '')
    expect(wrapper.findAll('.data-table-row')).toHaveLength(2)
    expect(wrapper.text()).toContain('deploy.sh')
    expect(wrapper.text()).toContain('backup.py')
    expect(wrapper.text()).toContain('shell')
    expect(wrapper.text()).toContain('python')
  })

  it('search input reloads list with keyword', async () => {
    const wrapper = mount(ScriptListView)
    await flushPromises()

    await wrapper.find('input.n-input').setValue('deploy')
    await flushPromises()

    expect(fetchScripts).toHaveBeenLastCalledWith(1, 20, 'deploy')
  })

  it('新建脚本 navigates to /scripts/new', async () => {
    const wrapper = mount(ScriptListView)
    await flushPromises()

    const btn = wrapper.findAll('button').find((b) => b.text().includes('新建脚本'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(push).toHaveBeenCalledWith('/scripts/new')
  })

  it('delete flow: confirm modal → deleteScript → success message → reload', async () => {
    const wrapper = mount(ScriptListView)
    await flushPromises()

    const row = wrapper.find('.data-table-row')
    const delBtn = row.findAll('button').find((b) => b.text() === '删除')
    expect(delBtn).toBeTruthy()
    await delBtn!.trigger('click')
    await nextTick()

    const modal = wrapper.find('.n-modal')
    expect(modal.exists()).toBe(true)
    expect(modal.text()).toContain('确认删除')
    expect(modal.text()).toContain('deploy.sh')

    const confirmBtn = modal.findAll('button').find((b) => b.text() === '删除')
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(deleteScript).toHaveBeenCalledWith(1)
    expect(messages[0].success).toHaveBeenCalledWith('删除成功')
    expect(wrapper.find('.n-modal').exists()).toBe(false)
    expect(fetchScripts).toHaveBeenCalledTimes(2) // 初始加载 + 删除后刷新
  })
})
