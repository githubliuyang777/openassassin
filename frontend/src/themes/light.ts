import type { GlobalThemeOverrides } from 'naive-ui'

export const lightTheme = {
  name: 'light',
  label: '经典明亮',
  icon: '☀️',
  naiveOverrides: {
    common: {
      primaryColor: '#2080f0',
      primaryColorHover: '#4098fc',
      primaryColorPressed: '#1060c9',
      primaryColorSuppl: '#4098fc',
      bodyColor: '#f5f7fa',
      cardColor: '#ffffff',
      modalColor: '#ffffff',
      popoverColor: '#ffffff',
      tableColor: '#ffffff',
      inputColor: '#ffffff',
      textColor1: '#333333',
      textColor2: '#555555',
      textColor3: '#999999',
      borderColor: '#e0e0e0',
      dividerColor: '#eeeeee',
      hoverColor: '#f5f5f5',
    },
    Layout: {
      headerColor: '#ffffff',
      siderColor: '#ffffff',
      footerColor: '#ffffff',
    },
    Card: {
      color: '#ffffff',
    },
    DataTable: {
      thColor: '#fafafa',
      tdColor: '#ffffff',
      borderColor: '#eeeeee',
    },
  } as GlobalThemeOverrides,
}
