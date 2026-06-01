import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import type { ScanStatus, CommitSizeMetrics, ReworkMetrics, AiCoauthorMetrics, Benchmarks } from '../types'
import { CommitSizeChart } from './CommitSizeChart'
import { AiCoauthorChart } from './AiCoauthorChart'
import { MetricCard } from './MetricCard'
import { useTheme } from '../ThemeContext'

interface Props {
  org: string
  repo: string
  initialStatus: ScanStatus
  commitSize: CommitSizeMetrics | null
  rework: ReworkMetrics | null
  aiCoauthor: AiCoauthorMetrics | null
  benchmarks: Benchmarks
  onScanComplete: () => void
}

export function DeepScanPanel({ org, repo, initialStatus, commitSize, rework, aiCoauthor, benchmarks, onScanComplete }: Props) {
  const { theme } = useTheme()
  const [status, setStatus] = useState<ScanStatus>(initialStatus)
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)

  const poll = useCallback(async () => {
    const state = await api.scanStatus(org, repo)
    setStatus(state.status)
    setProgress(state.status === 'scanning' ? { done: state.scanned_commits, total: state.total_commits } : null)
    if (state.status === 'done') onScanComplete()
  }, [org, repo, onScanComplete])

  useEffect(() => {
    if (status !== 'scanning') return
    const id = setInterval(poll, 2000)
    return () => clearInterval(id)
  }, [status, poll])

  async function startScan() {
    await api.triggerScan(org, repo)
    setStatus('scanning')
  }

  const btnStyle: React.CSSProperties = {
    background: theme.accent,
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    padding: '8px 16px',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 600,
  }

  if (status === 'idle' || status === 'error') {
    return (
      <div style={{ padding: '16px 0' }}>
        <button onClick={startScan} style={btnStyle}>
          {status === 'error' ? 'Retry deep scan' : 'Run deep scan (90d)'}
        </button>
        {status === 'error' && <span style={{ color: theme.critical, marginLeft: 12, fontSize: 12 }}>Last scan failed</span>}
      </div>
    )
  }

  if (status === 'scanning') {
    const pct = progress && progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0
    return (
      <div style={{ padding: '16px 0' }}>
        <div style={{ fontSize: 13, color: theme.textMuted }}>
          Scanning… {progress ? `${progress.done} / ${progress.total} commits` : 'starting'}
        </div>
        <div style={{ background: theme.borderStrong, borderRadius: 4, height: 6, marginTop: 8, width: '100%' }}>
          <div style={{ background: theme.accent, borderRadius: 4, height: 6, width: `${pct}%`, transition: 'width 0.4s' }} />
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {rework && (
          <MetricCard
            label="Rework rate (14d)"
            value={`${Math.round(rework.rate * 100)}%`}
            status={rework.status}
            sub={`threshold: ${Math.round(benchmarks.rework_rate.healthy * 100)}% / ${Math.round(benchmarks.rework_rate.warn * 100)}%`}
          />
        )}
        {commitSize && (
          <MetricCard
            label="Commit p50 churn"
            value={commitSize.p50}
            unit="lines"
            status={commitSize.status}
            sub={`p90: ${commitSize.p90} lines`}
          />
        )}
      </div>

      {commitSize && <CommitSizeChart data={commitSize} benchmarks={benchmarks} />}
      {aiCoauthor && <AiCoauthorChart data={aiCoauthor} />}

      {rework && rework.top_files.length > 0 && (
        <div>
          <div style={{ fontSize: 12, color: theme.textMuted, marginBottom: 6 }}>Top rework files</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <tbody>
              {rework.top_files.map(f => (
                <tr key={f.filename} style={{ borderBottom: `1px solid ${theme.border}` }}>
                  <td style={{ padding: '4px 8px', color: theme.textSecondary, fontFamily: 'monospace' }}>{f.filename}</td>
                  <td style={{ padding: '4px 8px', color: theme.warn, textAlign: 'right' }}>{f.rework_count}×</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <button onClick={startScan} style={{ ...btnStyle, background: 'transparent', border: `1px solid ${theme.borderStrong}`, color: theme.textDim, fontSize: 11 }}>
        Re-scan (delta only)
      </button>
    </div>
  )
}
