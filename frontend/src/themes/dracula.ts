import type { GlobalThemeOverrides } from 'naive-ui'

export const draculaTheme = {
  name: 'dracula',
  label: 'Dracula 紫暗',
  icon: '🧛',
  naiveOverrides: {
    common: {
      primaryColor: '#bd93f9',
      primaryColorHover: '#caa8fa',
      primaryColorPressed: '#ae7ef7',
      primaryColorSuppl: '#caa8fa',
      bodyColor: '#282a36',
      cardColor: '#282a36',
      modalColor: '#282a36',
      popoverColor: '#282a36',
      tableColor: '#282a36',
      inputColor: '#21222c',
      textColor1: '#f8f8f2',
      textColor2: '#bfbfbf',
      textColor3: '#6272a4',
      borderColor: '#44475a',
      dividerColor: '#44475a',
      hoverColor: '#343746',
    },
    Layout: {
      headerColor: '#21222c',
      siderColor: '#21222c',
      footerColor: '#21222c',
    },
    Card: {
      color: '#282a36',
    },
    DataTable: {
      thColor: '#21222c',
      tdColor: '#282a36',
      borderColor: '#44475a',
    },
  } as GlobalThemeOverrides,
}
