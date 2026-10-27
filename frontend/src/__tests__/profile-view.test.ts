import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
  auth: {
    user: { id: 1, username: 'admin', role: 'admin', email: '' },
    fetchMe: vi.fn(),
    fetchMfaStatus: vi.fn(),
    disableMfa: vi.fn(),
  },
  push: vi.fn(),
  fetchVersion: vi.fn(),
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
    NForm: slotComponent('form'),
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
      setup(props) {
        return () => h('span', props.value == null ? '' : String(props.value))
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
    NModal: defineComponent({
      name: 'NModal',
      props: { show: Boolean },
      setup(_, { slots }) {
        return () => h('div', slots.default?.())
      },
    }),
    useMessage: () => mocks.message,
  }
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mocks.auth,
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/api/client', () => ({
  api: { put: vi.fn() },
}))

vi.mock('@/api/system', () => ({
  fetchVersion: mocks.fetchVersion,
}))

import ProfileView from '@/views/ProfileView.vue'

beforeEach(() => {
  vi.resetAllMocks()
  mocks.auth.user = { id: 1, username: 'admin', role: 'admin', email: '' }
  mocks.auth.fetchMe.mockResolvedValue(undefined)
  mocks.auth.fetchMfaStatus.mockResolvedValue({
    totp_enabled: false,
    backup_codes_remaining: 0,
  })
})

describe('ProfileView website version', () => {
  it('shows the version for an admin', async () => {
    mocks.fetchVersion.mockResolvedValue({ version: 'v1.2.3' })

    const wrapper = mount(ProfileView)
    await flushPromises()

    expect(mocks.fetchVersion).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('网站版本')
    expect(wrapper.text()).toContain('v1.2.3')
  })

  it('does not request or show the version for a non-admin', async () => {
    mocks.auth.user = { id: 2, username: 'viewer', role: 'viewer', email: '' }

    const wrapper = mount(ProfileView)
    await flushPromises()

    expect(mocks.fetchVersion).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('网站版本')
  })
})
