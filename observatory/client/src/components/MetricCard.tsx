import { useTheme } from '../ThemeContext'
import type { HealthStatus } from '../types'

interface Props {
  label: string
  value: string | number | null
  unit?: string
  status?: HealthStatus | 'neutral'
  sub?: string
}

export function MetricCard({ label, value, unit, status = 'neutral', sub }: Props) {
  const { theme } = useTheme()
  const statusColor: Record<HealthStatus | 'neutral', string> = {
    healthy: theme.healthy,
    warn: theme.warn,
    critical: theme.critical,
    neutral: theme.textDim,
  }
  const color = statusColor[status]
  return (
    <div style={{
      background: theme.cardBg,
      border: `1px solid ${color}33`,
      borderRadius: 8,
      padding: '12px 16px',
      minWidth: 140,
    }}>
      <div style={{ fontSize: 11, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
      <div style={{ marginTop: 4, fontSize: 24, fontWeight: 700, color }}>
        {value ?? '—'}{unit && value !== null ? <span style={{ fontSize: 14, fontWeight: 400 }}> {unit}</span> : null}
      </div>
      {sub && <div style={{ fontSize: 11, color: theme.textDim, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}
