import { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { RepoDetail } from '../types'
import { MetricCard } from '../components/MetricCard'
import { DeepScanPanel } from '../components/DeepScanPanel'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useTheme } from '../ThemeContext'

export function RepoDetailPage() {
  const { org, repo } = useParams<{ org: string; repo: string }>()
  const navigate = useNavigate()
  const { theme } = useTheme()
  const [data, setData] = useState<RepoDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  type HotspotSort = 'complexity' | 'score' | 'body_lines'
  const [hotspotSort, setHotspotSort] = useState<HotspotSort>('complexity')

  const load = useCallback(async () => {
    if (!org || !repo) return
    try {
      const d = await api.repo(org, repo)
      setData(d)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [org, repo])

  useEffect(() => { void load() }, [load])

  const sortedHotspots = useMemo(() => {
    if (!data?.code_health) return []
    return [...data.code_health.hotspots].sort((a, b) => b[hotspotSort] - a[hotspotSort])
  }, [data, hotspotSort])

  const page: React.CSSProperties = {
    minHeight: '100vh',
    background: theme.pageBg,
    padding: 32,
    fontFamily: 'system-ui, sans-serif',
    maxWidth: 960,
    margin: '0 auto',
  }

  const section: React.CSSProperties = {
    marginTop: 32,
    padding: 20,
    background: theme.cardBg,
    border: `1px solid ${theme.border}`,
    borderRadius: 10,
  }

  const th: React.CSSProperties = {
    padding: '4px 8px',
    color: theme.textDim,
    fontWeight: 600,
    textAlign: 'left',
  }

  if (loading) return <div style={page}><div style={{ color: theme.textMuted }}>Loading…</div></div>
  if (error || !data) return <div style={page}><div style={{ color: theme.critical }}>{error}</div></div>

  const activityData = data.weekly_activity.map((count, i) => ({ week: `W${i + 1}`, count }))

  return (
    <div style={page}>
      <button onClick={() => navigate('/')} style={{ background: 'transparent', border: 'none', color: theme.textDim, cursor: 'pointer', fontSize: 13, padding: 0 }}>
        ← Overview
      </button>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: theme.textPrimary, marginTop: 16 }}>
        {org}/{repo}
      </h1>

      {/* Fast metrics row */}
      <div style={section}>
        <SectionTitle>Live</SectionTitle>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <MetricCard label="Open PRs" value={data.open_prs} />
          <MetricCard
            label="PR cycle time p50"
            value={data.pr_cycle_p50_hours !== null ? Math.round(data.pr_cycle_p50_hours) : null}
            unit="h"
            status={
              data.pr_cycle_p50_hours === null ? 'neutral'
              : data.pr_cycle_p50_hours > 72 ? 'critical'
              : data.pr_cycle_p50_hours > 24 ? 'warn'
              : 'healthy'
            }
          />
        </div>
      </div>

      {/* Commit activity */}
      <div style={section}>
        <SectionTitle>Commit activity (12 weeks)</SectionTitle>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart data={activityData}>
            <XAxis dataKey="week" tick={{ fontSize: 10, fill: theme.textDim }} />
            <YAxis tick={{ fontSize: 10, fill: theme.textDim }} />
            <Tooltip contentStyle={{ background: theme.cardBg, border: `1px solid ${theme.borderStrong}`, fontSize: 12 }} />
            <Bar dataKey="count" fill={theme.accent} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Contributors */}
      {data.contributors.length > 0 && (
        <div style={section}>
          <SectionTitle>Contributors (cached commits)</SectionTitle>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {data.contributors.map(c => (
              <div key={c.author} style={{ background: theme.pageBg, border: `1px solid ${theme.borderStrong}`, borderRadius: 6, padding: '4px 10px', fontSize: 12 }}>
                <span style={{ color: theme.textSecondary }}>{c.author}</span>
                <span style={{ color: theme.textDim, marginLeft: 6 }}>{c.commits}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Code hotspots */}
      {data.code_health && data.code_health.hotspots.length > 0 && (
        <div style={section}>
          <SectionTitle>Code hotspots (indxr)</SectionTitle>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${theme.borderStrong}` }}>
                <th style={th}>Function</th>
                <th style={th}>File</th>
                {(['score', 'complexity', 'body_lines'] as const).map(col => (
                  <th key={col} style={{ ...th, textAlign: 'right', cursor: 'pointer', userSelect: 'none',
                      color: hotspotSort === col ? theme.accentFg : theme.textDim }}
                    onClick={() => setHotspotSort(col)}>
                    {col === 'body_lines' ? 'Lines' : col.charAt(0).toUpperCase() + col.slice(1)}
                    {hotspotSort === col ? ' ↓' : ''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedHotspots.map((h, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${theme.border}` }}>
                  <td style={{ padding: '5px 8px', color: theme.textSecondary, fontFamily: 'monospace' }}>{h.name}</td>
                  <td style={{ padding: '5px 8px', color: theme.textDim, fontFamily: 'monospace' }}>{h.file}:{h.line}</td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', color: h.score >= 50 ? theme.critical : h.score >= 25 ? theme.warn : theme.textMuted, fontWeight: 600 }}>{h.score.toFixed(1)}</td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', color: h.complexity >= 20 ? theme.critical : h.complexity >= 10 ? theme.warn : theme.textMuted, fontWeight: hotspotSort === 'complexity' ? 600 : 400 }}>{h.complexity}</td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', color: theme.textMuted }}>{h.body_lines}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Deep scan */}
      <div style={section}>
        <SectionTitle>Deep scan</SectionTitle>
        {data.last_scanned_at && (
          <div style={{ fontSize: 11, color: theme.textFaint, marginBottom: 8 }}>
            Last scanned: {new Date(data.last_scanned_at).toLocaleString()}
          </div>
        )}
        <DeepScanPanel
          org={data.org}
          repo={repo!}
          initialStatus={data.scan_status}
          commitSize={data.commit_size}
          rework={data.rework}
          aiCoauthor={data.ai_coauthor}
          benchmarks={data.benchmarks}
          onScanComplete={load}
        />
      </div>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  const { theme } = useTheme()
  return <div style={{ fontSize: 12, fontWeight: 600, color: theme.textDim, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>{children}</div>
}
