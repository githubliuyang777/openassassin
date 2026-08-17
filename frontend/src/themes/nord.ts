import type { GlobalThemeOverrides } from 'naive-ui'

export const nordTheme = {
  name: 'nord',
  label: 'Nord 极光',
  icon: '❄️',
  naiveOverrides: {
    common: {
      primaryColor: '#88c0d0',
      primaryColorHover: '#8fccc0',
      primaryColorPressed: '#7fb8c8',
      primaryColorSuppl: '#8fccc0',
      bodyColor: '#2e3440',
      cardColor: '#3b4252',
      modalColor: '#3b4252',
      popoverColor: '#3b4252',
      tableColor: '#3b4252',
      inputColor: '#2e3440',
      textColor1: '#eceff4',
      textColor2: '#d8dee9',
      textColor3: '#7b88a1',
      borderColor: '#434c5e',
      dividerColor: '#434c5e',
      hoverColor: '#434c5e',
    },
    Layout: {
      headerColor: '#2e3440',
      siderColor: '#2e3440',
      footerColor: '#2e3440',
    },
    Card: {
      color: '#3b4252',
    },
    DataTable: {
      thColor: '#2e3440',
      tdColor: '#3b4252',
      borderColor: '#434c5e',
    },
  } as GlobalThemeOverrides,
}
