import type { RepoSummary, RepoDetail, ScanState, BenchmarkResults } from './types'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(path, { method: 'POST' })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  repos: () => get<RepoSummary[]>('/api/repos'),
  repo: (org: string, repo: string) => get<RepoDetail>(`/api/repos/${org}/${repo}`),
  scanStatus: (org: string, repo: string) => get<ScanState>(`/api/repos/${org}/${repo}/scan`),
  triggerScan: (org: string, repo: string) => post<{ started: boolean }>(`/api/repos/${org}/${repo}/scan`),
  benchmark: () => get<BenchmarkResults>('/api/benchmark'),
}
