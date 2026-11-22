import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  getSmtpStatus: vi.fn(),
  sendTestEmail: vi.fn(),
  getDingTalkStatus: vi.fn(),
  getDingTalkConfig: vi.fn(),
  updateDingTalkConfig: vi.fn(),
  testDingTalk: vi.fn(),
}))

vi.mock('naive-ui', async () => {
  const { defineComponent, h } = await vi.importActual<typeof import('vue')>('vue')

  const slotComponent = (tag: string) => defineComponent({
    name: tag,
    setup(_, { slots, attrs }) {
      return () => h(tag, attrs, slots.default ? slots.default() : undefined)
    },
  })

  return {
    NButton: slotComponent('button'),
    NCard: slotComponent('div'),
    NForm: defineComponent({
      name: 'NForm',
      setup(_, { slots, expose }) {
        expose({ validate: () => Promise.resolve(true) })
        return () => h('form', slots.default?.())
      },
    }),
    NFormItem: defineComponent({
      name: 'NFormItem',
      props: { label: String },
      setup(props, { slots }) {
        return () => h('div', [
          props.label ? h('span', props.label) : null,
          slots.default?.(),
        ])
      },
    }),
    NInput: defineComponent({
      name: 'NInput',
      props: { value: [String, Number] },
      emits: ['update:value'],
      setup(props, { emit }) {
        return () => h('input', {
          value: props.value,
          onInput: (event: Event) => emit(
            'update:value', (event.target as HTMLInputElement).value,
          ),
        })
      },
    }),
    NSelect: defineComponent({
      name: 'NSelect',
      props: { value: String, options: Array },
      setup(props) {
        return () => h('select', { value: props.value }, (props.options || []).map(
          (option: any) => h('option', {
            value: option.value,
            disabled: option.disabled,
          }, option.label),
        ))
      },
    }),
    NAlert: defineComponent({
      name: 'NAlert',
      props: { type: String, title: String },
      setup(props, { slots }) {
        return () => h('div', [
          props.title ? h('strong', props.title) : null,
          slots.default?.(),
        ])
      },
    }),
    NH2: slotComponent('h2'),
    NSpace: slotComponent('div'),
    NTag: slotComponent('span'),
    NDescriptions: slotComponent('div'),
    NDescriptionsItem: defineComponent({
      name: 'NDescriptionsItem',
      props: { label: String },
      setup(props, { slots }) {
        return () => h('div', [
          props.label ? h('span', props.label) : null,
          slots.default?.(),
        ])
      },
    }),
    NSpin: slotComponent('span'),
    NSwitch: slotComponent('span'),
  }
})

vi.mock('@/api/notifications', () => mocks)

import NotificationsView from '@/views/NotificationsView.vue'

function status(overrides: Record<string, any> = {}) {
  return {
    configured: true,
    alert_configured: true,
    transactional_configured: true,
    alert_failover_enabled: true,
    active_circuit: null,
    primary: {
      configured: true,
      host: 'smtp-primary.example.com',
      port: 587,
      from: 'primary@example.com',
      use_tls: true,
      health: 'closed',
      last_error: null,
      last_success_at: null,
    },
    fallback: {
      configured: true,
      host: 'smtp-fallback.example.com',
      port: 465,
      from: 'fallback@example.com',
      use_tls: true,
      health: 'open',
      last_error: 'connection refused',
      last_success_at: null,
    },
    host: 'smtp-primary.example.com',
    port: 587,
    from: 'primary@example.com',
    use_tls: true,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getSmtpStatus.mockResolvedValue(status())
  mocks.sendTestEmail.mockResolvedValue({
    message: '测试邮件已发送', provider: 'fallback', failover: true,
  })
  mocks.getDingTalkStatus.mockResolvedValue({ configured: false, enabled: false })
  mocks.getDingTalkConfig.mockResolvedValue({ webhook_url: '', is_enabled: false })
})

describe('NotificationsView SMTP failover', () => {
  it('shows both providers, circuit state and transactional email note', async () => {
    const wrapper = mount(NotificationsView)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('已启用（主 → 备）')
    expect(text).toContain('主 SMTP')
    expect(text).toContain('备用 SMTP')
    expect(text).toContain('smtp-primary.example.com')
    expect(text).toContain('smtp-fallback.example.com')
    expect(text).toContain('正常')
    expect(text).toContain('熔断')
    expect(text).toContain('connection refused')
    expect(text).toContain('密码重置/MFA 验证码仍只使用主 SMTP')
    expect(text).not.toContain('primary@example.com password')
  })

  it('disables the fallback test option when it is not configured', async () => {
    const unconfigured = status({
      alert_failover_enabled: false,
      fallback: {
        configured: false,
        host: null,
        port: null,
        from: null,
        use_tls: true,
        health: 'closed',
        last_error: null,
        last_success_at: null,
      },
    })
    mocks.getSmtpStatus.mockResolvedValue(unconfigured)

    const wrapper = mount(NotificationsView)
    await flushPromises()

    const options = wrapper.findAll('option')
    const fallbackOption = options.find(option => option.text().includes('备用 SMTP'))
    expect(fallbackOption).toBeDefined()
    expect(fallbackOption!.attributes('disabled')).toBeDefined()
  })

  it('sends the test email through auto failover with the entered address', async () => {
    const wrapper = mount(NotificationsView)
    await flushPromises()

    await wrapper.find('input').setValue('ops@example.com')
    const button = wrapper.findAll('button').find(item => item.text().includes('发送测试邮件'))
    expect(button).toBeDefined()
    await button!.trigger('click')
    await flushPromises()

    expect(mocks.sendTestEmail).toHaveBeenCalledWith('ops@example.com', 'auto')
    expect(wrapper.text()).toContain('发送成功')
  })
})
