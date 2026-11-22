import type { Config } from 'tailwindcss'

export default {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: 'var(--color-bg)',
        surface: 'var(--color-surface)',
        'surface-raised': 'var(--color-surface-raised)',
        border: 'var(--color-border)',
        'border-strong': 'var(--color-border-strong)',
        text: 'var(--color-text)',
        'text-muted': 'var(--color-text-muted)',
        accent: 'var(--color-accent)',
        'accent-contrast': 'var(--color-accent-contrast)',
        success: 'var(--color-success)',
        warning: 'var(--color-warning)',
        danger: 'var(--color-danger)',
        info: 'var(--color-info)',
      },
      fontFamily: {
        sans: 'var(--font-body)',
        display: 'var(--font-display)',
        mono: 'var(--font-mono)',
      },
      fontSize: {
        label: 'var(--type-label)',
        caption: 'var(--type-caption)',
        small: 'var(--type-small)',
        body: 'var(--type-body)',
        card: 'var(--type-card)',
        title: 'var(--type-title)',
        section: 'var(--type-section)',
        display: 'var(--type-display)',
      },
      spacing: {
        'page-gutter': 'var(--space-page-gutter)',
        'page-top': 'var(--space-page-top)',
        'grid-gap': 'var(--space-3)',
        'card-pad': 'var(--space-4)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        control: 'var(--radius-control)',
        DEFAULT: 'var(--radius)',
        pill: 'var(--radius-pill)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        focus: 'var(--shadow-focus)',
        status: 'var(--shadow-status)',
      },
    },
  },
  plugins: [],
} satisfies Config
