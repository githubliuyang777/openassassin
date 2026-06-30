<template>
  <n-layout style="height: 100vh">
    <n-layout-header bordered style="height: 56px; padding: 0 24px; display: flex; align-items: center; gap: 12px">
      <n-icon size="22" color="#2080f0"><ServerOutline /></n-icon>
      <n-text strong style="font-size: 17px">Ops Platform</n-text>
      <n-space style="margin-left: auto" align="center">
        <n-text depth="3">{{ user?.username }}</n-text>
        <n-button text @click="handleLogout">退出</n-button>
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
</template>

<script setup lang="ts">
import { computed, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  NLayout, NLayoutHeader, NLayoutSider, NLayoutContent,
  NMenu, NIcon, NText, NButton, NSpace,
} from 'naive-ui'
import {
  ServerOutline,
  CodeSlashOutline,
  KeyOutline,
  BarChartOutline,
  TimeOutline,
} from '@vicons/ionicons5'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const user = computed(() => auth.user)

const menuOptions = [
  { label: '概览', key: 'Dashboard', icon: () => h(NIcon, null, () => h(BarChartOutline)) },
  { label: '脚本管理', key: 'Scripts', icon: () => h(NIcon, null, () => h(CodeSlashOutline)) },
  { label: '密钥管理', key: 'Credentials', icon: () => h(NIcon, null, () => h(KeyOutline)) },
  { label: '执行历史', key: 'Executions', icon: () => h(NIcon, null, () => h(TimeOutline)) },
]

function activeKeyFromPath() {
  if (route.path.startsWith('/scripts')) return 'Scripts'
  if (route.path.startsWith('/credentials')) return 'Credentials'
  if (route.path.startsWith('/executions')) return 'Executions'
  return 'Dashboard'
}

const activeKey = computed(activeKeyFromPath)

function handleMenu(key: string) {
  router.push(`/${key.toLowerCase()}`)
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>
