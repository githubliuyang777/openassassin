import { lightTheme } from './light'
import { darkTheme } from './dark'
import { draculaTheme } from './dracula'
import { nordTheme } from './nord'

export interface ThemeConfig {
  name: string
  label: string
  icon: string
  naiveOverrides: any
}

export const themes: Record<string, ThemeConfig> = {
  light: lightTheme,
  dark: darkTheme,
  dracula: draculaTheme,
  nord: nordTheme,
}

export const themeList = Object.values(themes)

export function getTheme(name: string): ThemeConfig {
  return themes[name] || lightTheme
}
