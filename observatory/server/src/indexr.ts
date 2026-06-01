import { execFile } from 'child_process'
import { promisify } from 'util'
import { getDb } from './db'

const execFileAsync = promisify(execFile)
const INDXR_BIN = process.env.INDXR_BIN ?? 'indxr'
const CACHE_TTL_MS = 60 * 60 * 1000 // 1 hour

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

export interface CodeHealth {
  hotspots: Hotspot[]
}

export async function getCodeHealth(org: string, repo: string, localPath: string, limit = 15): Promise<CodeHealth | null> {
  const db = getDb()

  const cached = db
    .prepare('SELECT hotspots, cached_at FROM code_health_cache WHERE org=? AND repo=?')
    .get(org, repo) as { hotspots: string; cached_at: string } | undefined

  if (cached && Date.now() - new Date(cached.cached_at).getTime() < CACHE_TTL_MS) {
    return { hotspots: JSON.parse(cached.hotspots) }
  }

  try {
    const { stdout } = await execFileAsync(INDXR_BIN, [localPath, '--hotspots'], { timeout: 15000 })
    const hotspots = parseHotspots(stdout, limit)
    db.prepare(`
      INSERT INTO code_health_cache (org, repo, hotspots, cached_at)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(org, repo) DO UPDATE SET hotspots=excluded.hotspots, cached_at=excluded.cached_at
    `).run(org, repo, JSON.stringify(hotspots), new Date().toISOString())
    return { hotspots }
  } catch {
    return null
  }
}

function parseHotspots(output: string, limit: number): Hotspot[] {
  const results: Hotspot[] = []
  for (const line of output.split('\n')) {
    if (!line.trim() || line.includes('Score') || line.startsWith('-')) continue
    // "   77.0    1     0      2   1500  path/file.js:13  fnName"
    const m = line.match(/^\s*([\d.]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+):(\d+)\s+(.+)$/)
    if (!m) continue
    results.push({
      score: parseFloat(m[1]),
      complexity: parseInt(m[2]),
      nesting: parseInt(m[3]),
      params: parseInt(m[4]),
      body_lines: parseInt(m[5]),
      file: m[6],
      line: parseInt(m[7]),
      name: m[8].trim(),
    })
    if (results.length >= limit) break
  }
  return results
}
