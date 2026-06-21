/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Cyan accent (primary brand)
        'cyan-accent': {
          DEFAULT: 'var(--color-cyan-accent)',
          hover: 'var(--color-cyan-accent-hover)',
        },
        // Primary (black/near-black)
        primary: {
          DEFAULT: 'var(--color-primary)',
          hover: 'var(--color-primary-hover)',
        },
        // Semantic status colors
        success: {
          DEFAULT: 'var(--color-success-hex)',
          light: 'var(--color-success-light-hex)',
        },
        warning: {
          DEFAULT: 'var(--color-warning)',
          light: 'var(--color-warning-light-hex)',
        },
        danger: {
          DEFAULT: 'var(--color-danger-hex)',
          light: 'var(--color-danger-light-hex)',
        },
        info: {
          DEFAULT: 'var(--color-info-hex)',
          light: 'var(--color-info-light-hex)',
        },
        // Surface colors
        surface: 'var(--bg-surface)',
        elevated: 'var(--bg-elevated)',
        sidebar: 'var(--bg-sidebar)',
        code: 'var(--bg-code)',
        // Blueprint
        'blueprint-grid': 'var(--blueprint-grid)',
        'blueprint-grid-strong': 'var(--blueprint-grid-strong)',
        // Text colors
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-tertiary': 'var(--text-tertiary)',
        'text-inverse': 'var(--text-inverse)',
        // Border colors
        'border-default': 'var(--border-default)',
        'border-subtle': 'var(--border-subtle)',
      },
      fontFamily: {
        mono: ['IBM Plex Mono', 'Fira Code', 'Consolas', 'Monaco', 'monospace'],
      },
      fontSize: {
        xs: ['0.6875rem', { lineHeight: '1.25' }],
        sm: ['0.75rem', { lineHeight: '1.25' }],
        base: ['0.8125rem', { lineHeight: '1.5' }],
        lg: ['0.875rem', { lineHeight: '1.5' }],
        xl: ['1rem', { lineHeight: '1.4' }],
        '2xl': ['1.125rem', { lineHeight: '1.3' }],
        '3xl': ['1.5rem', { lineHeight: '1.2' }],
        '4xl': ['1.75rem', { lineHeight: '1.1' }],
      },
      spacing: {
        15: '3.75rem',   // 240px sidebar width
        64: '16rem',
        72: '18rem',
        80: '20rem',
      },
      borderRadius: {
        none: '0px',
        sm: '0px',
        md: '0px',
        lg: '0px',
        xl: '0px',
      },
      boxShadow: {
        none: 'none',
      },
      transitionTimingFunction: {
        'expo-out': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      transitionDuration: {
        fast: '100ms',
        normal: '150ms',
        slow: '300ms',
      },
      zIndex: {
        sidebar: '40',
        overlay: '50',
        modal: '60',
        toast: '70',
      },
    },
  },
  plugins: [],
};
