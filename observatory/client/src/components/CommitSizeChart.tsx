import { BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
import { useTheme } from '../ThemeContext'
import type { CommitSizeMetrics, Benchmarks } from '../types'

interface Props {
  data: CommitSizeMetrics
  benchmarks: Benchmarks
}

export function CommitSizeChart({ data, benchmarks }: Props) {
  const { theme } = useTheme()
  return (
    <div>
      <div style={{ fontSize: 12, color: theme.textMuted, marginBottom: 8 }}>
        Commit size distribution — p50: <strong>{data.p50}</strong> lines, p90: <strong>{data.p90}</strong> lines
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data.distribution} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
          <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: theme.textMuted }} />
          <YAxis tick={{ fontSize: 11, fill: theme.textMuted }} />
          <Tooltip contentStyle={{ background: theme.cardBg, border: `1px solid ${theme.borderStrong}`, fontSize: 12 }} />
          <Bar dataKey="count" fill={theme.accent} radius={[3, 3, 0, 0]} />
          <ReferenceLine
            x={bucketForChurn(benchmarks.commit_size.healthy_p50)}
            stroke={theme.healthy}
            strokeDasharray="4 2"
            label={{ value: 'healthy p50', fill: theme.healthy, fontSize: 10 }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function bucketForChurn(churn: number): string {
  if (churn < 10) return '0–9'
  if (churn < 50) return '10–49'
  if (churn < 100) return '50–99'
  if (churn < 200) return '100–199'
  if (churn < 500) return '200–499'
  if (churn < 1000) return '500–999'
  return '1000+'
}
