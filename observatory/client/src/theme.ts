export interface Theme {
  pageBg: string
  cardBg: string
  border: string
  borderStrong: string
  accent: string
  accentFg: string
  accentSecondary: string
  textPrimary: string
  textSecondary: string
  textMuted: string
  textDim: string
  textFaint: string
  healthy: string
  warn: string
  critical: string
}

export const themes: Record<string, Theme> = {
  indigo: {
    pageBg: '#111827',
    cardBg: '#1e1e2e',
    border: '#1f2937',
    borderStrong: '#374151',
    accent: '#6366f1',
    accentFg: '#a5b4fc',
    accentSecondary: '#a78bfa',
    textPrimary: '#f9fafb',
    textSecondary: '#e5e7eb',
    textMuted: '#9ca3af',
    textDim: '#6b7280',
    textFaint: '#4b5563',
    healthy: '#22c55e',
    warn: '#f59e0b',
    critical: '#ef4444',
  },
  orange: {
    pageBg: '#111211',
    cardBg: '#1c1917',
    border: '#292524',
    borderStrong: '#44403c',
    accent: '#f97316',
    accentFg: '#fdba74',
    accentSecondary: '#fb923c',
    textPrimary: '#fafaf9',
    textSecondary: '#e7e5e4',
    textMuted: '#a8a29e',
    textDim: '#78716c',
    textFaint: '#57534e',
    healthy: '#22c55e',
    warn: '#eab308',
    critical: '#ef4444',
  },
  emerald: {
    pageBg: '#0d1512',
    cardBg: '#131f1a',
    border: '#1a2e22',
    borderStrong: '#2d4a38',
    accent: '#10b981',
    accentFg: '#6ee7b7',
    accentSecondary: '#34d399',
    textPrimary: '#f9fafb',
    textSecondary: '#e5e7eb',
    textMuted: '#9ca3af',
    textDim: '#6b7280',
    textFaint: '#4b5563',
    healthy: '#22c55e',
    warn: '#f59e0b',
    critical: '#ef4444',
  },
}

export type ThemeName = keyof typeof themes
