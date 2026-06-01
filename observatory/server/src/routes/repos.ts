import fs from 'fs'
import path from 'path'
import { Router } from 'express'
import { getRepos, getBenchmarks, getMailmap, getHarnessSourcePath } from '../config'
import { getDb } from '../db'
import { fetchRecentActivity, fetchOpenPrCount, fetchAgentFiles } from '../github'

function getCurrentHarnessVersion(): string | null {
  const sourcePath = getHarnessSourcePath()
  if (!sourcePath) return null
  try {
    const pyproject = fs.readFileSync(path.join(sourcePath, 'pyproject.toml'), 'utf8')
    const match = pyproject.match(/^version\s*=\s*"([^"]+)"/m)
    return match ? match[1] : null
  } catch {
    return null
  }
}

function findPluginDir(localPath: string): { dir: string; pluginDir: string } | null {
  const claudeDir = path.join(localPath, '.claude')
  if (!fs.existsSync(claudeDir)) return null
  try {
    for (const entry of fs.readdirSync(claudeDir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue
      const manifestPath = path.join(claudeDir, entry.name, '.claude-plugin', 'plugin.json')
      if (fs.existsSync(manifestPath)) return { dir: entry.name, pluginDir: path.join(claudeDir, entry.name) }
    }
  } catch { /* ignore */ }
  return null
}

function getHarnessStatus(localPath?: string): {
  installed: boolean
  plugin_dir: string | null
  installed_version: string | null
  current_version: string | null
  up_to_date: boolean | null
  built_at: string | null
} {
  const current_version = getCurrentHarnessVersion()
  const none = { installed: false, plugin_dir: null, installed_version: null, current_version, up_to_date: null, built_at: null }
  if (!localPath) return none

  const found = findPluginDir(localPath)
  if (!found) return none

  try {
    const metaPath = path.join(found.pluginDir, '.harness-meta.json')
    const meta = fs.existsSync(metaPath) ? JSON.parse(fs.readFileSync(metaPath, 'utf8')) : {}
    const manifest = JSON.parse(fs.readFileSync(path.join(found.pluginDir, '.claude-plugin', 'plugin.json'), 'utf8'))
    const installed_version = meta.harness_version ?? manifest.version ?? null
    const up_to_date = current_version && installed_version ? current_version === installed_version : null
    return { installed: true, plugin_dir: found.dir, installed_version, current_version, up_to_date, built_at: meta.built_at ?? null }
  } catch {
    return { installed: true, plugin_dir: found.dir, installed_version: null, current_version, up_to_date: null, built_at: null }
  }
}

export const reposRouter = Router()

reposRouter.get('/', async (req, res) => {
  const repos = getRepos()
  const bm = getBenchmarks()
  const mailmap = getMailmap()
  const aiPatterns = bm.ai_patterns.map(p => new RegExp(p, 'i'))
  const db = getDb()

  const results = await Promise.allSettled(
    repos.map(async ({ org, repo, display_name, local_path }) => {
      const [activity, openPrs, agentFiles] = await Promise.all([
        fetchRecentActivity(org, repo, aiPatterns, mailmap, 12),
        fetchOpenPrCount(org, repo),
        fetchAgentFiles(org, repo),
      ])

      const last4 = activity.weekly_counts.slice(-4)
      const commits_last_30d = last4.reduce((a, b) => a + b, 0)

      const scanState = db
        .prepare('SELECT status, scanned_commits, total_commits, last_scanned_at FROM scan_state WHERE org=? AND repo=?')
        .get(org, repo) as { status: string; scanned_commits: number; total_commits: number; last_scanned_at: string } | undefined

      // Commit size p50/p90 from cache (deep scan)
      const churns = (
        db.prepare('SELECT additions+deletions AS churn FROM commits WHERE org=? AND repo=? ORDER BY churn').all(org, repo) as { churn: number }[]
      ).map(r => r.churn)
      const p50 = churns.length ? churns[Math.floor(churns.length * 0.5)] : null
      const p90 = churns.length ? churns[Math.floor(churns.length * 0.9)] : null

      // Rework rate from cache
      const reworkState = db
        .prepare("SELECT status FROM scan_state WHERE org=? AND repo=? AND status='done'")
        .get(org, repo) as { status: string } | undefined

      return {
        org,
        repo,
        display_name,
        commits_per_week: activity.weekly_counts,
        commits_last_30d,
        open_prs: openPrs,
        last_commit_date: activity.last_commit_date,
        last_commit_message: activity.last_commit_message,
        last_commit_author: activity.last_commit_author,
        top_authors: activity.top_authors,
        ai_pct: activity.total_commit_count > 0
          ? activity.ai_commit_count / activity.total_commit_count
          : null,
        dirty_authors: activity.dirty_authors,
        agent_files: agentFiles,
        commit_size: p50 !== null ? { p50, p90 } : null,
        harness: getHarnessStatus(local_path),
        has_deep_scan: !!reworkState,
        scan_status: scanState?.status ?? 'idle',
        scan_progress: scanState?.status === 'scanning'
          ? { done: scanState.scanned_commits, total: scanState.total_commits }
          : null,
        last_scanned_at: scanState?.last_scanned_at ?? null,
      }
    })
  )

  const data = results.map((r, i) =>
    r.status === 'fulfilled' ? r.value : { ...repos[i], error: (r.reason as Error).message }
  )

  res.json(data)
})
