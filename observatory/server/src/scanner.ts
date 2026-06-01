import { getDb } from './db'
import { fetchCommitList, fetchCommitDetail, sleep } from './github'

const SCAN_WINDOW_DAYS = 90
const BATCH_SIZE = 10
const BATCH_DELAY_MS = 200

export async function runDeepScan(org: string, repo: string): Promise<void> {
  const db = getDb()

  const existing = db
    .prepare('SELECT last_scanned_at, last_commit_sha FROM scan_state WHERE org=? AND repo=?')
    .get(org, repo) as { last_scanned_at: string | null; last_commit_sha: string | null } | undefined

  const since = existing?.last_scanned_at
    ?? new Date(Date.now() - SCAN_WINDOW_DAYS * 24 * 60 * 60 * 1000).toISOString()

  db.prepare(`
    INSERT INTO scan_state (org, repo, status, scanned_commits, total_commits)
    VALUES (?, ?, 'scanning', 0, 0)
    ON CONFLICT(org, repo) DO UPDATE SET status='scanning', scanned_commits=0, total_commits=0
  `).run(org, repo)

  const commits = await fetchCommitList(org, repo, since)

  // Filter out already-cached SHAs
  const cachedShas = new Set(
    (db.prepare('SELECT sha FROM commits WHERE org=? AND repo=?').all(org, repo) as { sha: string }[])
      .map(r => r.sha)
  )
  const toFetch = commits.filter(c => !cachedShas.has(c.sha))

  db.prepare(
    'UPDATE scan_state SET total_commits=? WHERE org=? AND repo=?'
  ).run(toFetch.length, org, repo)

  const insertCommit = db.prepare(`
    INSERT OR REPLACE INTO commits (org, repo, sha, date, author, message, additions, deletions)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `)
  const insertFile = db.prepare(`
    INSERT INTO commit_files (org, repo, sha, filename, additions, deletions)
    VALUES (?, ?, ?, ?, ?, ?)
  `)
  const deleteFiles = db.prepare('DELETE FROM commit_files WHERE org=? AND repo=? AND sha=?')

  let done = 0
  for (let i = 0; i < toFetch.length; i += BATCH_SIZE) {
    const batch = toFetch.slice(i, i + BATCH_SIZE)

    await Promise.all(
      batch.map(async c => {
        const detail = await fetchCommitDetail(org, repo, c.sha)

        const upsert = db.transaction(() => {
          deleteFiles.run(org, repo, c.sha)
          insertCommit.run(org, repo, c.sha, c.date, c.author, c.message, detail.additions, detail.deletions)
          for (const f of detail.files) {
            insertFile.run(org, repo, c.sha, f.filename, f.additions, f.deletions)
          }
        })
        upsert()
      })
    )

    done += batch.length
    db.prepare('UPDATE scan_state SET scanned_commits=? WHERE org=? AND repo=?').run(done, org, repo)

    if (i + BATCH_SIZE < toFetch.length) await sleep(BATCH_DELAY_MS)
  }

  const latest = commits[0]
  db.prepare(`
    UPDATE scan_state
    SET status='done', last_scanned_at=?, last_commit_sha=?
    WHERE org=? AND repo=?
  `).run(new Date().toISOString(), latest?.sha ?? existing?.last_commit_sha ?? null, org, repo)
}
