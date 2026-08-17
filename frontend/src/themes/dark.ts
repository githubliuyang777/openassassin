import type { GlobalThemeOverrides } from 'naive-ui'

export const darkTheme = {
  name: 'dark',
  label: '深邃暗黑',
  icon: '🌙',
  naiveOverrides: {
    common: {
      primaryColor: '#63e2b7',
      primaryColorHover: '#7fe7c7',
      primaryColorPressed: '#4cdba7',
      primaryColorSuppl: '#7fe7c7',
      bodyColor: '#1a1a2e',
      cardColor: '#16213e',
      modalColor: '#16213e',
      popoverColor: '#16213e',
      tableColor: '#16213e',
      inputColor: '#0f3460',
      textColor1: '#e0e0e0',
      textColor2: '#b0b0b0',
      textColor3: '#808080',
      borderColor: '#2a2a4a',
      dividerColor: '#2a2a4a',
      hoverColor: '#1f2b47',
    },
    Layout: {
      headerColor: '#0f3460',
      siderColor: '#0f3460',
      footerColor: '#0f3460',
    },
    Card: {
      color: '#16213e',
    },
    DataTable: {
      thColor: '#0f3460',
      tdColor: '#16213e',
      borderColor: '#2a2a4a',
    },
  } as GlobalThemeOverrides,
}
