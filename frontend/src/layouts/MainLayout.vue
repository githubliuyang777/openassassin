<template>
  <n-layout style="height: 100vh">
    <n-layout-header bordered style="height: 56px; padding: 0 24px; display: flex; align-items: center; gap: 12px">
      <n-icon size="22" color="#2080f0"><ServerOutline /></n-icon>
      <n-text strong style="font-size: 17px">Ops Platform</n-text>
      <n-space style="margin-left: auto" align="center">
        <n-dropdown trigger="click" :options="userMenuOptions" @select="handleUserMenu">
          <n-button text>
            {{ user?.username }}
            <n-icon style="margin-left: 4px"><ChevronDownOutline /></n-icon>
          </n-button>
        </n-dropdown>
      </n-space>
    </n-layout-header>
    <n-layout has-sider style="flex: 1">
      <n-layout-sider bordered width="200">
        <n-menu :value="activeKey" :options="menuOptions" @update:value="handleMenu" />
      </n-layout-sider>
      <n-layout-content content-style="padding: 24px">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>

  <!-- Change Password Modal -->
  <n-modal v-model:show="showPasswordModal" preset="card" title="修改密码" style="width: 420px">
    <n-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-placement="top">
      <n-form-item path="oldPassword" label="旧密码">
        <n-input v-model:value="pwdForm.oldPassword" type="password" />
      </n-form-item>
      <n-form-item path="newPassword" label="新密码">
        <n-input v-model:value="pwdForm.newPassword" type="password" placeholder="至少6位" />
      </n-form-item>
      <n-form-item path="confirmPassword" label="确认新密码">
        <n-input v-model:value="pwdForm.confirmPassword" type="password" />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="showPasswordModal = false">取消</n-button>
        <n-button type="primary" :loading="changingPwd" @click="handleChangePassword">确认修改</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  NLayout, NLayoutHeader, NLayoutSider, NLayoutContent,
  NMenu, NIcon, NText, NButton, NSpace, NDropdown, NModal, NForm, NFormItem, NInput, useMessage,
} from 'naive-ui'
import {
  ServerOutline,
  CodeSlashOutline,
  KeyOutline,
  BarChartOutline,
  TimeOutline,
  ChevronDownOutline,
  SettingsOutline,
} from '@vicons/ionicons5'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const message = useMessage()

const user = computed(() => auth.user)
const showPasswordModal = ref(false)
const changingPwd = ref(false)
const pwdFormRef = ref()

const pwdForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const validateConfirm = (_rule: any, value: string) => {
  if (value !== pwdForm.value.newPassword) {
    return new Error('两次输入的密码不一致')
  }
  return true
}

const pwdRules = {
  oldPassword: [{ required: true, message: '请输入旧密码' }],
  newPassword: [
    { required: true, message: '请输入新密码' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

const userMenuOptions = [
  { label: '修改密码', key: 'change-password' },
  { type: 'divider', key: 'd1' },
  { label: '退出登录', key: 'logout' },
]

function handleUserMenu(key: string) {
  if (key === 'logout') {
    auth.logout()
    router.push('/login')
  } else if (key === 'change-password') {
    pwdForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
    showPasswordModal.value = true
  }
}

async function handleChangePassword() {
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid) return
  changingPwd.value = true
  try {
    await auth.changePassword(pwdForm.value.oldPassword, pwdForm.value.newPassword)
    message.success('密码修改成功，请重新登录')
    showPasswordModal.value = false
    router.push('/login')
  } catch (e: any) {
    message.error(e.message || '修改失败')
  } finally {
    changingPwd.value = false
  }
}

const menuOptions = [
  { label: '概览', key: 'Dashboard', icon: () => h(NIcon, null, () => h(BarChartOutline)) },
  { label: '脚本管理', key: 'Scripts', icon: () => h(NIcon, null, () => h(CodeSlashOutline)) },
  { label: '密钥管理', key: 'Credentials', icon: () => h(NIcon, null, () => h(KeyOutline)) },
  { label: '执行历史', key: 'Executions', icon: () => h(NIcon, null, () => h(TimeOutline)) },
  {
    label: '系统',
    key: 'System',
    icon: () => h(NIcon, null, () => h(SettingsOutline)),
    children: [
      { label: '消息通知', key: 'system-notifications' },
    ],
  },
]

function activeKeyFromPath() {
  if (route.path.startsWith('/scripts')) return 'Scripts'
  if (route.path.startsWith('/credentials')) return 'Credentials'
  if (route.path.startsWith('/executions')) return 'Executions'
  if (route.path.startsWith('/system')) return 'system-notifications'
  return 'Dashboard'
}

const activeKey = computed(activeKeyFromPath)

function handleMenu(key: string) {
  if (key === 'system-notifications') {
    router.push('/system/notifications')
    return
  }
  router.push(`/${key.toLowerCase()}`)
}
</script>
