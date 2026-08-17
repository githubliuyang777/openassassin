<template>
  <n-config-provider :theme-overrides="themeStore.naiveOverrides" :theme="naiveTheme" :locale="zhCN" :date-locale="dateZhCN">
    <n-loading-bar-provider>
      <n-message-provider>
        <n-dialog-provider>
          <router-view />
        </n-dialog-provider>
      </n-message-provider>
    </n-loading-bar-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { zhCN, dateZhCN, darkTheme } from 'naive-ui'
import {
  NConfigProvider,
  NLoadingBarProvider,
  NMessageProvider,
  NDialogProvider,
} from 'naive-ui'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
const naiveTheme = computed(() => themeStore.isDark ? darkTheme : undefined)
</script>
