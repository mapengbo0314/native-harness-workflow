import fs from 'fs'
import path from 'path'
import { Router } from 'express'
import { getHarnessSourcePath } from '../config'

interface ResultJson {
  model: string
  condition_id: string
  case_id: string
  test_result: { success: boolean }
  case_metadata: { difficulty: string }
}

interface ConditionStats {
  label: string
  pass: number
  total: number
  rate: number
}

interface DifficultyCondMap {
  [condId: string]: { pass: number; total: number }
}

interface ModelStats {
  label: string
  cases_total: number
  conditions: { [condId: string]: ConditionStats }
  delta_pp: number
  by_difficulty: { [diff: string]: DifficultyCondMap }
}

interface BenchmarkResults {
  generated_at: string
  runs_count: number
  models: { [modelId: string]: ModelStats }
}

const CONDITION_LABELS: Record<string, string> = {
  claude: 'baseline',
  'claude-harness': 'harness',
  'claude-ecc': 'ecc',
}

const MODEL_LABELS: Record<string, string> = {
  'claude-haiku-4-5-20251001': 'Haiku',
  'claude-sonnet-4-6': 'Sonnet',
}

function findResultFiles(runsDir: string): string[] {
  const results: string[] = []
  try {
    const entries = fs.readdirSync(runsDir, { withFileTypes: true })
    for (const entry of entries) {
      if (!entry.isDirectory()) continue
      const candidate = path.join(runsDir, entry.name, 'result.json')
      if (fs.existsSync(candidate)) results.push(candidate)
    }
  } catch {
    /* runs dir missing — return empty */
  }
  return results
}

function parseResult(filePath: string): ResultJson | null {
  try {
    const raw = fs.readFileSync(filePath, 'utf8')
    return JSON.parse(raw) as ResultJson
  } catch {
    return null
  }
}

function computeStats(files: string[]): BenchmarkResults['models'] {
  // key: `${model}|${conditionPrefix}|${caseId}` → best pass (true beats false)
  const best = new Map<string, boolean>()

  for (const file of files) {
    const r = parseResult(file)
    if (!r || !r.model || !r.condition_id || !r.case_id) continue
    const condPrefix = r.condition_id.split(':')[0]
    const key = `${r.model}|${condPrefix}|${r.case_id}`
    const success = r.test_result?.success ?? false
    const prev = best.get(key)
    if (prev === undefined || (!prev && success)) {
      best.set(key, success)
    }
  }

  // Aggregate per model + condition
  const modelMap = new Map<string, { label: string; condPass: Map<string, { pass: number; total: number }>; diffCond: Map<string, Map<string, { pass: number; total: number }>>; caseIds: Set<string> }>()

  // Re-iterate files to get difficulty
  const meta = new Map<string, { difficulty: string }>()
  for (const file of files) {
    const r = parseResult(file)
    if (!r || !r.model || !r.condition_id || !r.case_id) continue
    const condPrefix = r.condition_id.split(':')[0]
    const key = `${r.model}|${condPrefix}|${r.case_id}`
    const difficulty = r.case_metadata?.difficulty ?? 'unknown'
    if (!meta.has(key)) meta.set(key, { difficulty })
  }

  for (const [key, success] of best) {
    const [model, condPrefix, caseId] = key.split('|')
    if (!MODEL_LABELS[model]) continue // skip unknown models

    if (!modelMap.has(model)) {
      modelMap.set(model, {
        label: MODEL_LABELS[model],
        condPass: new Map(),
        diffCond: new Map(),
        caseIds: new Set(),
      })
    }

    const m = modelMap.get(model)!
    m.caseIds.add(caseId)

    const cp = m.condPass.get(condPrefix) ?? { pass: 0, total: 0 }
    cp.total += 1
    if (success) cp.pass += 1
    m.condPass.set(condPrefix, cp)

    const difficulty = meta.get(key)?.difficulty ?? 'unknown'
    if (!m.diffCond.has(difficulty)) m.diffCond.set(difficulty, new Map())
    const dc = m.diffCond.get(difficulty)!
    const dcp = dc.get(condPrefix) ?? { pass: 0, total: 0 }
    dcp.total += 1
    if (success) dcp.pass += 1
    dc.set(condPrefix, dcp)
  }

  const models: BenchmarkResults['models'] = {}

  for (const [model, m] of modelMap) {
    const conditions: ModelStats['conditions'] = {}
    for (const [condId, stats] of m.condPass) {
      conditions[condId] = {
        label: CONDITION_LABELS[condId] ?? condId,
        pass: stats.pass,
        total: stats.total,
        rate: stats.total > 0 ? stats.pass / stats.total : 0,
      }
    }

    const baselineRate = conditions['claude']?.rate ?? 0
    const harnessRate = conditions['claude-harness']?.rate ?? 0
    const delta_pp = Math.round((harnessRate - baselineRate) * 1000) / 10

    const by_difficulty: ModelStats['by_difficulty'] = {}
    for (const [diff, dc] of m.diffCond) {
      by_difficulty[diff] = {}
      for (const [condId, stats] of dc) {
        by_difficulty[diff][condId] = { pass: stats.pass, total: stats.total }
      }
    }

    models[model] = {
      label: m.label,
      cases_total: m.caseIds.size,
      conditions,
      delta_pp,
      by_difficulty,
    }
  }

  return models
}

export const benchmarkRouter = Router()

benchmarkRouter.get('/benchmark', (_req, res) => {
  const sourcePath = getHarnessSourcePath()
  if (!sourcePath) {
    const empty: BenchmarkResults = { generated_at: new Date().toISOString(), runs_count: 0, models: {} }
    res.json(empty)
    return
  }

  const runsDir = path.join(sourcePath, 'benchmark', 'harness-bench', 'benchmark', 'runs')
  const files = findResultFiles(runsDir)
  const models = computeStats(files)

  const result: BenchmarkResults = {
    generated_at: new Date().toISOString(),
    runs_count: files.length,
    models,
  }
  res.json(result)
})
