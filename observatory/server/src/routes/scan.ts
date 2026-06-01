import { Router } from 'express'
import { getDb } from '../db'
import { runDeepScan } from '../scanner'

export const scanRouter = Router()

// Trigger a deep scan (non-blocking)
scanRouter.post('/:org/:repo/scan', async (req, res) => {
  const { org, repo } = req.params
  const db = getDb()

  const state = db
    .prepare('SELECT status FROM scan_state WHERE org=? AND repo=?')
    .get(org, repo) as { status: string } | undefined

  if (state?.status === 'scanning') {
    return res.status(409).json({ error: 'Scan already in progress' })
  }

  // Fire and forget — client polls for progress
  runDeepScan(org, repo).catch(err => {
    db.prepare("UPDATE scan_state SET status='error' WHERE org=? AND repo=?").run(org, repo)
    console.error(`Scan failed for ${org}/${repo}:`, err)
  })

  res.json({ started: true })
})

// Poll scan state
scanRouter.get('/:org/:repo/scan', (req, res) => {
  const { org, repo } = req.params
  const db = getDb()

  const state = db
    .prepare('SELECT status, scanned_commits, total_commits, last_scanned_at FROM scan_state WHERE org=? AND repo=?')
    .get(org, repo) as { status: string; scanned_commits: number; total_commits: number; last_scanned_at: string } | undefined

  res.json(state ?? { status: 'idle', scanned_commits: 0, total_commits: 0, last_scanned_at: null })
})
