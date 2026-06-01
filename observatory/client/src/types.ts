export type HealthStatus = 'healthy' | 'warn' | 'critical'
export type ScanStatus = 'idle' | 'scanning' | 'done' | 'error'

export interface RepoSummary {
  org: string
  repo: string
  display_name: string
  commits_per_week: number[]
  commits_last_30d: number
  open_prs: number
  last_commit_date: string | null
  last_commit_message: string | null
  last_commit_author: string | null
  top_authors: { name: string; count: number }[]
  ai_pct: number | null
  commit_size: { p50: number; p90: number } | null
  dirty_authors: { raw_name: string; email: string; count: number }[]
  agent_files: { claude_md: boolean; agents_md: boolean }
  harness: {
    installed: boolean
    plugin_dir: string | null
    installed_version: string | null
    current_version: string | null
    up_to_date: boolean | null
    built_at: string | null
  } | null
  has_deep_scan: boolean
  scan_status: ScanStatus
  scan_progress: { done: number; total: number } | null
  last_scanned_at: string | null
  error?: string
}

export interface PrSummary {
  number: number
  title: string
  merged_at: string | null
  cycle_time_hours: number | null
}

export interface Benchmarks {
  commit_size: { healthy_p50: number; warn_p50: number; healthy_p90: number; warn_p90: number }
  pr_size: { healthy_lines: number; warn_lines: number }
  rework_rate: { healthy: number; warn: number }
  ai_patterns: string[]
}

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

export interface Hotspot {
  score: number
  complexity: number
  nesting: number
  params: number
  body_lines: number
  file: string
  line: number
  name: string
}

export interface RepoDetail {
  org: string
  repo: string
  weekly_activity: number[]
  open_prs: number
  pr_cycle_p50_hours: number | null
  recent_prs: PrSummary[]
  contributors: { author: string; commits: number }[]
  scan_status: ScanStatus
  scan_progress: { done: number; total: number } | null
  last_scanned_at: string | null
  commit_size: CommitSizeMetrics | null
  rework: ReworkMetrics | null
  ai_coauthor: AiCoauthorMetrics | null
  benchmarks: Benchmarks
  code_health: { hotspots: Hotspot[] } | null
}

export interface ScanState {
  status: ScanStatus
  scanned_commits: number
  total_commits: number
  last_scanned_at: string | null
}
