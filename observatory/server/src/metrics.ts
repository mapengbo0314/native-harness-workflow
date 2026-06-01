import { getDb } from './db'
import { getBenchmarks } from './config'

export type HealthStatus = 'healthy' | 'warn' | 'critical'

export interface CommitSizeMetrics {
  p50: number
  p90: number
  status: HealthStatus
  distribution: { bucket: string; count: number }[]
}

export interface ReworkMetrics {
  rate: number
  status: HealthStatus
  top_files: { filename: string; rework_count: number }[]
}

export interface AiCoauthorMetrics {
  pct: number
  by_week: { week: string; pct: number }[]
}

const CHURN_BUCKETS = [
  { label: '0–9', max: 9 },
  { label: '10–49', max: 49 },
  { label: '50–99', max: 99 },
  { label: '100–199', max: 199 },
  { label: '200–499', max: 499 },
  { label: '500–999', max: 999 },
  { label: '1000+', max: Infinity },
]

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0
  const idx = Math.ceil((p / 100) * sorted.length) - 1
  return sorted[Math.max(0, idx)]
}

export function computeCommitSize(org: string, repo: string): CommitSizeMetrics {
  const db = getDb()
  const bm = getBenchmarks()

  const rows = db
    .prepare('SELECT additions+deletions AS churn FROM commits WHERE org=? AND repo=? ORDER BY churn')
    .all(org, repo) as { churn: number }[]

  const churns = rows.map(r => r.churn)
  const p50 = percentile(churns, 50)
  const p90 = percentile(churns, 90)

  let status: HealthStatus = 'healthy'
  if (p50 > bm.commit_size.warn_p50 || p90 > bm.commit_size.warn_p90) status = 'critical'
  else if (p50 > bm.commit_size.healthy_p50 || p90 > bm.commit_size.healthy_p90) status = 'warn'

  const distribution = CHURN_BUCKETS.map(({ label, max }, i) => {
    const min = i === 0 ? 0 : CHURN_BUCKETS[i - 1].max + 1
    return { bucket: label, count: churns.filter(c => c >= min && c <= max).length }
  })

  return { p50, p90, status, distribution }
}

export function computeRework(org: string, repo: string, windowDays = 14): ReworkMetrics {
  const db = getDb()
  const bm = getBenchmarks()

  // Load all (sha, filename, date) sorted by filename then date
  const rows = db.prepare(`
    SELECT cf.sha, cf.filename, c.date
    FROM commit_files cf
    JOIN commits c ON c.org=cf.org AND c.repo=cf.repo AND c.sha=cf.sha
    WHERE cf.org=? AND cf.repo=?
    ORDER BY cf.filename, c.date
  `).all(org, repo) as { sha: string; filename: string; date: string }[]

  const reworkShas = new Set<string>()
  const fileReworkCount: Record<string, number> = {}
  const windowMs = windowDays * 24 * 60 * 60 * 1000

  let prev: { filename: string; date: string } | null = null
  for (const row of rows) {
    if (prev && prev.filename === row.filename) {
      const diff = new Date(row.date).getTime() - new Date(prev.date).getTime()
      if (diff > 0 && diff <= windowMs) {
        reworkShas.add(row.sha)
        fileReworkCount[row.filename] = (fileReworkCount[row.filename] ?? 0) + 1
      }
    }
    prev = { filename: row.filename, date: row.date }
  }

  const total = (db.prepare('SELECT COUNT(*) AS n FROM commits WHERE org=? AND repo=?').get(org, repo) as { n: number }).n
  const rate = total > 0 ? reworkShas.size / total : 0

  let status: HealthStatus = 'healthy'
  if (rate > bm.rework_rate.warn) status = 'critical'
  else if (rate > bm.rework_rate.healthy) status = 'warn'

  const top_files = Object.entries(fileReworkCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([filename, rework_count]) => ({ filename, rework_count }))

  return { rate, status, top_files }
}

export function computeAiCoauthor(
  org: string,
  repo: string,
  patterns: RegExp[],
): AiCoauthorMetrics {
  const db = getDb()

  const rows = db
    .prepare('SELECT sha, message, date FROM commits WHERE org=? AND repo=? ORDER BY date DESC')
    .all(org, repo) as { sha: string; message: string; date: string }[]

  const isAi = (msg: string) => patterns.some(p => p.test(msg))

  const total = rows.length
  const aiCount = rows.filter(r => isAi(r.message)).length
  const pct = total > 0 ? aiCount / total : 0

  // Group by ISO week
  const byWeek: Record<string, { ai: number; total: number }> = {}
  for (const r of rows) {
    const week = isoWeek(r.date)
    if (!byWeek[week]) byWeek[week] = { ai: 0, total: 0 }
    byWeek[week].total++
    if (isAi(r.message)) byWeek[week].ai++
  }

  const by_week = Object.entries(byWeek)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([week, { ai, total }]) => ({ week, pct: total > 0 ? ai / total : 0 }))

  return { pct, by_week }
}

function isoWeek(dateStr: string): string {
  const d = new Date(dateStr)
  const day = d.getUTCDay() || 7
  d.setUTCDate(d.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
  const week = Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, '0')}`
}
