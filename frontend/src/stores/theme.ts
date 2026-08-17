import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getTheme, themeList } from '@/themes'
import type { ThemeConfig } from '@/themes'

export const useThemeStore = defineStore('theme', () => {
  const currentTheme = ref(localStorage.getItem('theme') || 'light')

  const themeConfig = computed<ThemeConfig>(() => getTheme(currentTheme.value))
  const naiveOverrides = computed(() => themeConfig.value.naiveOverrides)
  const isDark = computed(() => currentTheme.value !== 'light')

  function setTheme(name: string) {
    currentTheme.value = name
    localStorage.setItem('theme', name)
    document.documentElement.setAttribute('data-theme', name)
  }

  // Initialize on load
  document.documentElement.setAttribute('data-theme', currentTheme.value)

  return {
    currentTheme,
    themeConfig,
    naiveOverrides,
    isDark,
    themeList,
    setTheme,
  }
})
