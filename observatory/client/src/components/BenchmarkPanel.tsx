import { useEffect, useState } from 'react'
import { api } from '../api'
import type { BenchmarkResults, BenchmarkModel } from '../types'
import { useTheme } from '../ThemeContext'

const COND_ORDER = ['claude', 'claude-harness', 'claude-ecc'] as const
const DIFF_ORDER = ['low', 'mid', 'high'] as const

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function pct(rate: number): string {
  return `${Math.round(rate * 100)}%`
}

function DeltaBadge({ pp }: { pp: number }) {
  const color = pp > 0 ? '#22c55e' : pp < 0 ? '#ef4444' : '#6b7280'
  const arrow = pp > 0 ? '▲' : pp < 0 ? '▼' : '='
  const sign = pp > 0 ? '+' : ''
  return (
    <span style={{ color, fontSize: 11, fontWeight: 700, marginLeft: 4 }}>
      {sign}{pp}pp {arrow}
    </span>
  )
}

function ModelRow({ data }: { model: string; data: BenchmarkModel }) {
  const { theme } = useTheme()
  const baseline = data.conditions['claude']
  const harness = data.conditions['claude-harness']
  const ecc = data.conditions['claude-ecc']
  const harnessVsBaseline = baseline && harness
    ? Math.round((harness.rate - baseline.rate) * 1000) / 10
    : null
  const eccVsBaseline = baseline && ecc
    ? Math.round((ecc.rate - baseline.rate) * 1000) / 10
    : null

  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, fontSize: 13, flexWrap: 'wrap' }}>
      <span style={{ color: theme.textPrimary, fontWeight: 600, minWidth: 56 }}>{data.label}</span>
      {COND_ORDER.map(condId => {
        const c = data.conditions[condId]
        if (!c) return null
        const delta = condId === 'claude-harness' ? harnessVsBaseline
          : condId === 'claude-ecc' ? eccVsBaseline
          : null
        return (
          <span key={condId} style={{ color: theme.textSecondary }}>
            <span style={{ color: theme.textMuted, fontSize: 11 }}>{c.label} </span>
            <span style={{ fontWeight: 600 }}>{pct(c.rate)}</span>
            {delta !== null && <DeltaBadge pp={delta} />}
            <span style={{ color: theme.borderStrong, marginLeft: 8 }}>·</span>
          </span>
        )
      })}
    </div>
  )
}

function DifficultyTable({ models }: { models: BenchmarkResults['models'] }) {
  const { theme } = useTheme()
  const modelIds = Object.keys(models)

  return (
    <table style={{ borderCollapse: 'collapse', fontSize: 11, width: '100%', marginTop: 8 }}>
      <thead>
        <tr>
          <th style={{ textAlign: 'left', color: theme.textFaint, fontWeight: 400, paddingRight: 16, paddingBottom: 4 }}>By difficulty</th>
          {DIFF_ORDER.map(d => (
            <th key={d} style={{ color: theme.textFaint, fontWeight: 400, paddingRight: 12, paddingBottom: 4, textAlign: 'center' }}>
              {d[0].toUpperCase() + d.slice(1)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {modelIds.map(modelId => {
          const m = models[modelId]
          const harness = m.conditions['claude-harness']
          if (!harness) return null
          return (
            <tr key={modelId}>
              <td style={{ color: theme.textMuted, paddingRight: 16, paddingBottom: 2 }}>
                {m.label} harness
              </td>
              {DIFF_ORDER.map(diff => {
                const dc = m.by_difficulty[diff]
                const hc = dc?.['claude-harness']
                const bc = m.by_difficulty[diff]?.['claude']
                const harnessRate = hc ? hc.pass / (hc.total || 1) : null
                const baseRate = bc ? bc.pass / (bc.total || 1) : null
                const delta = harnessRate !== null && baseRate !== null
                  ? Math.round((harnessRate - baseRate) * 100)
                  : null
                const arrow = delta === null ? '' : delta > 0 ? ' ▲' : delta < 0 ? ' ▼' : ' ='
                const color = delta === null ? theme.textFaint
                  : delta > 0 ? '#22c55e'
                  : delta < 0 ? '#ef4444'
                  : theme.textMuted
                return (
                  <td key={diff} style={{ textAlign: 'center', paddingRight: 12, paddingBottom: 2 }}>
                    {harnessRate !== null
                      ? <span style={{ color }}>{pct(harnessRate)}{arrow}</span>
                      : <span style={{ color: theme.textFaint }}>—</span>
                    }
                  </td>
                )
              })}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export function BenchmarkPanel() {
  const { theme } = useTheme()
  const [data, setData] = useState<BenchmarkResults | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.benchmark()
      .then(setData)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  const card: React.CSSProperties = {
    background: theme.cardBg,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: '14px 20px',
    marginBottom: 10,
  }

  if (loading) return (
    <div style={card}>
      <span style={{ color: theme.textMuted, fontSize: 12 }}>Loading benchmark data…</span>
    </div>
  )

  if (error || !data) return (
    <div style={card}>
      <span style={{ color: theme.critical, fontSize: 12 }}>Benchmark data unavailable{error ? `: ${error}` : ''}</span>
    </div>
  )

  if (data.runs_count === 0) return (
    <div style={card}>
      <span style={{ color: theme.textFaint, fontSize: 12 }}>No benchmark runs found.</span>
    </div>
  )

  const modelCount = Object.keys(data.models).length
  const caseCount = Object.values(data.models)[0]?.cases_total ?? 0

  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, color: theme.textFaint, textTransform: 'uppercase' as const }}>
            Harness Benchmark
          </span>
          <span style={{ fontSize: 11, color: theme.textFaint }}>
            {caseCount} cases · {modelCount} models
          </span>
        </div>
        <span style={{ fontSize: 10, color: theme.textFaint }}>updated {timeAgo(data.generated_at)}</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
        {Object.entries(data.models).map(([id, m]) => (
          <ModelRow key={id} model={id} data={m} />
        ))}
      </div>

      <DifficultyTable models={data.models} />

      <div style={{ marginTop: 10, fontSize: 11, color: theme.textDim }}>
        <span style={{ color: theme.accentFg }}>i</span>
        {' '}Harness wins on high-difficulty bugs. Regresses on easy tasks.
      </div>
    </div>
  )
}
