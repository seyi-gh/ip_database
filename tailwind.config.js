/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./static/**/*.html'],
  theme: {
    extend: {
      fontFamily: {
        'code-md':    ['JetBrains Mono'],
        'display-lg': ['Geist'],
        'body-lg':    ['Geist'],
        'headline-lg':['Geist'],
        'label-sm':   ['JetBrains Mono'],
        'body-md':    ['Geist'],
        'headline-md':['Geist'],
      },
      fontSize: {
        'code-md':     ['14px', { lineHeight: '1.7',  fontWeight: '400' }],
        'display-lg':  ['48px', { lineHeight: '1.1',  letterSpacing: '-0.02em', fontWeight: '700' }],
        'body-lg':     ['16px', { lineHeight: '1.6',  fontWeight: '400' }],
        'headline-lg': ['32px', { lineHeight: '1.2',  letterSpacing: '-0.01em', fontWeight: '600' }],
        'label-sm':    ['12px', { lineHeight: '1.0',  fontWeight: '500' }],
        'body-md':     ['14px', { lineHeight: '1.5',  fontWeight: '400' }],
        'headline-md': ['24px', { lineHeight: '1.3',  fontWeight: '600' }],
      },
      colors: {
        'on-surface':         '#d4e4fa',
        'on-surface-variant': '#c8c4d7',
        'outline-variant':    '#474555',
        'surface':            '#051424',
        'surface-container-low': '#0d1c2d',
        'primary':            '#c7bfff',
        'secondary':          '#5adace',
      },
    },
  },
  plugins: [],
}
