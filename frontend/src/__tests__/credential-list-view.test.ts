import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'

const { messages } = vi.hoisted(() => ({ messages: [] as Array<{ success: any; error: any; warning: any }> }))

// 阻止真实 api client 导入链（router/pinia）
vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/api/credentials', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/credentials')>()
  return {
    ...actual,
    fetchCredentials: vi.fn(),
    createCredential: vi.fn(),
    revealCredential: vi.fn(),
    deleteCredential: vi.fn(),
    toggleCredentialAlert: vi.fn(),
    parseKubeconfig: vi.fn(),
  }
})

vi.mock('@/api/notification-groups', () => ({
  fetchGroups: vi.fn(),
}))

vi.mock('naive-ui', async () => {
  const vue = await vi.importActual<typeof import('vue')>('vue')
  const { defineComponent: def, h: hh } = vue

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
    props: ['modelValue', 'type'],
    emits: ['update:value'],
    setup(props: any, { emit }: any) {
      const isTextarea = props.type === 'textarea'
      return () =>
        isTextarea
          ? hh('textarea', {
            class: 'n-input',
            value: props.modelValue ?? '',
            onInput: (e: Event) => emit('update:value', (e.target as HTMLTextAreaElement).value),
          })
          : hh('input', {
            class: 'n-input',
            value: props.modelValue ?? '',
            onInput: (e: Event) => emit('update:value', (e.target as HTMLInputElement).value),
          })
    },
  })

  const NSelect = def({
    name: 'NSelect',
    props: ['modelValue', 'options'],
    emits: ['update:value'],
    setup(props: any, { emit }: any) {
      return () =>
        hh('select', {
          class: 'n-select',
          value: props.modelValue ?? '',
          onChange: (e: Event) => emit('update:value', (e.target as HTMLSelectElement).value),
        }, (props.options || []).map((o: any) => hh('option', { value: String(o.value) }, o.label)))
    },
  })

  const NSwitch = def({
    name: 'NSwitch',
    props: ['value', 'modelValue'],
    emits: ['update:value'],
    setup(props: any, { emit }: any) {
      const v = props.modelValue !== undefined ? props.modelValue : props.value
      return () => hh('button', { class: 'n-switch', onClick: () => emit('update:value', !v) }, String(v))
    },
  })

  const NForm = def({
    name: 'NForm',
    setup(_: unknown, { slots, expose }: any) {
      expose({ validate: () => Promise.resolve(true) })
      return () => hh('form', { class: 'n-form' }, slots.default?.())
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

  const NDatePicker = def({
    name: 'NDatePicker',
    props: ['formattedValue'],
    setup() {
      return () => null
    },
  })

  return {
    NH3: Slot('NH3'),
    NSpace: Slot('NSpace'),
    NIcon: Slot('NIcon'),
    NTag: Slot('NTag'),
    NText: Slot('NText'),
    NFormItem: Slot('NFormItem'),
    NGrid: Slot('NGrid'),
    NGridItem: Slot('NGridItem'),
    NDescriptions: Slot('NDescriptions'),
    NDescriptionsItem: Slot('NDescriptionsItem'),
    NButton,
    NInput,
    NSelect,
    NSwitch,
    NForm,
    NDataTable,
    NModal,
    NDatePicker,
    useMessage: () => {
      const m = { success: vi.fn(), error: vi.fn(), warning: vi.fn() }
      messages.push(m)
      return m
    },
  }
})

import CredentialListView from '@/views/CredentialListView.vue'
import {
  fetchCredentials, createCredential, revealCredential, deleteCredential, toggleCredentialAlert,
  parseKubeconfig,
} from '@/api/credentials'
import { fetchGroups } from '@/api/notification-groups'

const CRED_ROWS = [
  {
    id: 1, name: 'prod-token', key: 'PROD_TOKEN', description: '生产环境', type: 'api_token',
    expires_at: '2099-12-31T00:00:00', alert_enabled: true, notification_group_id: null,
    created_at: '2026-07-01T00:00:00', updated_at: '2026-07-01T00:00:00',
  },
  {
    id: 2, name: 'k8s-config', key: 'K8S_CONFIG', description: '', type: 'kubeconfig',
    expires_at: null, alert_enabled: true, notification_group_id: null,
    created_at: '2026-07-01T00:00:00', updated_at: '2026-07-01T00:00:00',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  messages.length = 0
  vi.mocked(fetchCredentials).mockResolvedValue({ data: CRED_ROWS } as any)
  vi.mocked(fetchGroups).mockResolvedValue({ data: [] } as any)
})

describe('CredentialListView', () => {
  it('renders credentials and loads notification groups on mount', async () => {
    const wrapper = mount(CredentialListView)
    await flushPromises()

    expect(fetchCredentials).toHaveBeenCalledTimes(1)
    expect(fetchGroups).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('.data-table-row')).toHaveLength(2)
    expect(wrapper.text()).toContain('prod-token')
    expect(wrapper.text()).toContain('PROD_TOKEN')
    expect(wrapper.text()).toContain('k8s-config')
  })

  it('create flow: fill form → createCredential with payload → success message', async () => {
    const wrapper = mount(CredentialListView)
    await flushPromises()

    const createBtn = wrapper.findAll('button').find((b) => b.text().includes('新建密钥'))
    await createBtn!.trigger('click')
    await nextTick()

    const modal = wrapper.find('.n-modal')
    expect(modal.exists()).toBe(true)
    expect(modal.text()).toContain('新建密钥')

    const inputs = modal.findAll('.n-input')
    expect(inputs.length).toBeGreaterThanOrEqual(3) // name / key / value(textarea) / description
    await inputs[0].setValue('prod-token')
    await inputs[1].setValue('PROD_TOKEN')
    await inputs[2].setValue('shh-secret')
    await inputs[3].setValue('生产环境')

    vi.mocked(createCredential).mockResolvedValue({ data: { id: 3 } } as any)
    const saveBtn = modal.findAll('button').find((b) => b.text() === '保存')
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(createCredential).toHaveBeenCalledWith(expect.objectContaining({
      name: 'prod-token',
      key: 'PROD_TOKEN',
      value: 'shh-secret',
      description: '生产环境',
      type: 'generic',
      alert_enabled: true,
    }))
    expect(messages[0].success).toHaveBeenCalledWith('创建成功')
    expect(wrapper.find('.n-modal').exists()).toBe(false)
    expect(fetchCredentials).toHaveBeenCalledTimes(2) // 初始 + 创建后刷新
  })

  it('reveal flow: 查看 → value masked by default → 显示 reveals plaintext', async () => {
    const wrapper = mount(CredentialListView)
    await flushPromises()

    vi.mocked(revealCredential).mockResolvedValue({ data: { ...CRED_ROWS[0], value: "revealed-secret-xyz" } } as any)
    const row = wrapper.find('.data-table-row')
    const viewBtn = row.findAll('button').find((b) => b.text() === '查看')
    await viewBtn!.trigger('click')
    await flushPromises()

    expect(revealCredential).toHaveBeenCalledWith(1)
    const modal = wrapper.find('.n-modal')
    // 默认掩码，明文不直接展示
    expect(modal.text()).toContain('••••••••••••')
    expect(modal.text()).not.toContain('revealed-secret-xyz')

    // 点击"显示"后明文可见
    const showBtn = modal.findAll('button').find((b) => b.text() === '显示')
    await showBtn!.trigger('click')
    await nextTick()
    expect(modal.text()).toContain('revealed-secret-xyz')
  })

  it('toggle alert switch calls API and shows message', async () => {
    const wrapper = mount(CredentialListView)
    await flushPromises()

    vi.mocked(toggleCredentialAlert).mockResolvedValue({ data: { ...CRED_ROWS[0], alert_enabled: false } } as any)
    const row = wrapper.find('.data-table-row') // prod-token, expires_at 存在 → 有开关
    const switchBtn = row.find('.n-switch')
    expect(switchBtn.exists()).toBe(true)

    await switchBtn.trigger('click')
    await flushPromises()

    expect(toggleCredentialAlert).toHaveBeenCalledWith(1, false)
    expect(messages[0].success).toHaveBeenCalledWith('已关闭告警通知')
  })

  it('delete flow: confirm modal → deleteCredential → success message', async () => {
    const wrapper = mount(CredentialListView)
    await flushPromises()

    vi.mocked(deleteCredential).mockResolvedValue({} as any)
    const row = wrapper.find('.data-table-row')
    const delBtn = row.findAll('button').find((b) => b.text() === '删除')
    await delBtn!.trigger('click')
    await nextTick()

    const modal = wrapper.find('.n-modal')
    expect(modal.text()).toContain('确认删除')
    expect(modal.text()).toContain('prod-token')

    const confirmBtn = modal.findAll('button').find((b) => b.text() === '删除')
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(deleteCredential).toHaveBeenCalledWith(1)
    expect(messages[0].success).toHaveBeenCalledWith('删除成功')
  })

  it('parse-kubeconfig guard: empty value warns without calling API', async () => {
    const wrapper = mount(CredentialListView)
    await flushPromises()

    // 打开新建弹窗, 将类型切换为 kubeconfig
    const createBtn = wrapper.findAll('button').find((b) => b.text().includes('新建密钥'))
    await createBtn!.trigger('click')
    await nextTick()

    const typeSelect = wrapper.find('select.n-select') // 第一个 select 是类型
    await typeSelect.setValue('kubeconfig')
    await nextTick()

    const parseBtn = wrapper.findAll('button').find((b) => b.text().includes('自动解析'))
    expect(parseBtn).toBeTruthy()
    await parseBtn!.trigger('click')
    await nextTick()

    expect(messages[0].warning).toHaveBeenCalledWith('请先填入 kubeconfig 内容')
    expect(parseKubeconfig).not.toHaveBeenCalled()
  })

  it('parse-kubeconfig flow: value filled → API called → expires_at set + success message', async () => {
    const wrapper = mount(CredentialListView)
    await flushPromises()

    const createBtn = wrapper.findAll('button').find((b) => b.text().includes('新建密钥'))
    await createBtn!.trigger('click')
    await nextTick()

    const typeSelect = wrapper.find('select.n-select')
    await typeSelect.setValue('kubeconfig')
    await nextTick()

    // 填入 kubeconfig 内容
    const inputs = wrapper.find('.n-modal').findAll('.n-input')
    await inputs[2].setValue('apiVersion: v1\nkind: Config\n')

    vi.mocked(parseKubeconfig).mockResolvedValue({
      data: { expires_at: '2026-10-01T00:00:00', days_left: 60 },
    } as any)
    const parseBtn = wrapper.findAll('button').find((b) => b.text().includes('自动解析'))
    await parseBtn!.trigger('click')
    await flushPromises()

    expect(parseKubeconfig).toHaveBeenCalledWith('apiVersion: v1\nkind: Config\n')
    expect(messages[0].success).toHaveBeenCalledWith(expect.stringContaining('已解析有效期'))
  })
})
