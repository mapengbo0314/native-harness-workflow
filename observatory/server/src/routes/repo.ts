import { Router } from 'express'
import { getBenchmarks, getMailmap, getRepos } from '../config'
import { fetchRecentActivity, fetchOpenPrCount, fetchRecentPrs } from '../github'
import { computeCommitSize, computeRework, computeAiCoauthor } from '../metrics'
import { getDb } from '../db'
import { getCodeHealth } from '../indexr'

export const repoRouter = Router()

repoRouter.get('/:org/:repo', async (req, res) => {
  const { org, repo } = req.params
  const bm = getBenchmarks()
  const aiPatterns = bm.ai_patterns.map(p => new RegExp(p, 'i'))
  const db = getDb()

  const mailmap = getMailmap()
  const repoConfig = getRepos().find(r => r.org === org && r.repo === repo)

  const [activity, openPrs, recentPrs, codeHealth] = await Promise.all([
    fetchRecentActivity(org, repo, aiPatterns, mailmap, 12),
    fetchOpenPrCount(org, repo),
    fetchRecentPrs(org, repo),
    repoConfig?.local_path ? getCodeHealth(org, repo, repoConfig.local_path) : Promise.resolve(null),
  ])

  const scanState = db
    .prepare('SELECT status, scanned_commits, total_commits, last_scanned_at FROM scan_state WHERE org=? AND repo=?')
    .get(org, repo) as { status: string; scanned_commits: number; total_commits: number; last_scanned_at: string } | undefined

  const hasCache = !!scanState && scanState.status === 'done'

  const commitSize = hasCache ? computeCommitSize(org, repo) : null
  const rework = hasCache ? computeRework(org, repo) : null
  const aiCoauthor = hasCache ? computeAiCoauthor(org, repo, aiPatterns) : null

  // PR cycle time summary
  const cycle_times = recentPrs.map(p => p.cycle_time_hours).filter((h): h is number => h !== null)
  const pr_cycle_p50 = cycle_times.length
    ? cycle_times.sort((a, b) => a - b)[Math.floor(cycle_times.length * 0.5)]
    : null

  // Contributor breakdown from cached commits
  const contributors = db.prepare(`
    SELECT author, COUNT(*) AS commits
    FROM commits WHERE org=? AND repo=?
    GROUP BY author ORDER BY commits DESC LIMIT 10
  `).all(org, repo) as { author: string; commits: number }[]

  res.json({
    org,
    repo,
    weekly_activity: activity.weekly_counts,
    open_prs: openPrs,
    pr_cycle_p50_hours: pr_cycle_p50,
    recent_prs: recentPrs.slice(0, 20),
    contributors,
    scan_status: scanState?.status ?? 'idle',
    scan_progress: scanState?.status === 'scanning'
      ? { done: scanState.scanned_commits, total: scanState.total_commits }
      : null,
    last_scanned_at: scanState?.last_scanned_at ?? null,
    commit_size: commitSize,
    rework,
    ai_coauthor: aiCoauthor,
    benchmarks: bm,
    code_health: codeHealth,
  })
})
