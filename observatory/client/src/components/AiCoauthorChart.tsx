import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
import { useTheme } from '../ThemeContext'
import type { AiCoauthorMetrics } from '../types'

interface Props {
  data: AiCoauthorMetrics
}

export function AiCoauthorChart({ data }: Props) {
  const { theme } = useTheme()
  const chartData = data.by_week.slice(-16).map(w => ({
    week: w.week.replace(/^\d{4}-/, ''),
    pct: Math.round(w.pct * 100),
  }))

  return (
    <div>
      <div style={{ fontSize: 12, color: theme.textMuted, marginBottom: 8 }}>
        AI co-author % by week — overall: <strong>{Math.round(data.pct * 100)}%</strong>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
          <XAxis dataKey="week" tick={{ fontSize: 10, fill: theme.textMuted }} interval={1} />
          <YAxis tick={{ fontSize: 11, fill: theme.textMuted }} domain={[0, 100]} unit="%" />
          <Tooltip
            formatter={(v: number) => [`${v}%`, 'AI co-author']}
            contentStyle={{ background: theme.cardBg, border: `1px solid ${theme.borderStrong}`, fontSize: 12 }}
          />
          <ReferenceLine y={50} stroke={theme.warn} strokeDasharray="4 2" />
          <Line type="monotone" dataKey="pct" stroke={theme.accentSecondary} dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
