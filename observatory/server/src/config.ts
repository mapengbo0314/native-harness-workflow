import fs from 'fs'
import path from 'path'
import yaml from 'js-yaml'

const ROOT = path.join(__dirname, '../..')

export interface RepoConfig {
  org: string
  repo: string
  display_name: string
  local_path?: string
}

export interface Benchmarks {
  commit_size: { healthy_p50: number; warn_p50: number; healthy_p90: number; warn_p90: number }
  pr_size: { healthy_lines: number; warn_lines: number }
  rework_rate: { healthy: number; warn: number }
  ai_patterns: string[]
}

function load<T>(filename: string): T {
  const raw = fs.readFileSync(path.join(ROOT, filename), 'utf8')
  return yaml.load(raw) as T
}

interface MailmapEntry {
  emails?: string[]
  names?: string[]
}

export type Mailmap = Record<string, MailmapEntry>

export function getRepos(): RepoConfig[] {
  const data = load<{ repos: RepoConfig[] }>('repos.yaml')
  return data.repos.map(r => ({ ...r, display_name: r.display_name ?? `${r.org}/${r.repo}` }))
}

export function getHarnessSourcePath(): string | undefined {
  const data = load<{ harness_source_path?: string }>('repos.yaml')
  return data.harness_source_path
}

export function getBenchmarks(): Benchmarks {
  return load<Benchmarks>('benchmarks.yaml')
}

export function getMailmap(): Mailmap {
  return load<Mailmap>('mailmap.yaml')
}

/** Resolve a raw git author name + email to a canonical name, or null if unrecognized. */
export function resolveAuthor(name: string, email: string, mailmap: Mailmap): string | null {
  const emailLower = email.toLowerCase()
  const nameLower = name.toLowerCase()
  for (const [canonical, entry] of Object.entries(mailmap)) {
    if (entry.emails?.some(e => e.toLowerCase() === emailLower)) return canonical
    if (entry.names?.some(n => n.toLowerCase() === nameLower)) return canonical
    if (canonical.toLowerCase() === nameLower) return canonical
  }
  return null
}
