/**
 * Fold the per-route sweep records into one catalog + a human report (#969).
 *
 * Reads every `sweep-results/records/*.json` written by `visitAndCatalog`,
 * emits:
 *   - `sweep-results/sweep-catalog.json` — the machine catalog (all records +
 *     a summary by outcome and by area).
 *   - `sweep-results/SWEEP-CATALOG.md`   — a skimmable coverage report to paste
 *     into the #969 tracking issue / PR body.
 *
 * Plain ESM (`.mjs`) on purpose: runs under bare `node` with no transpile step,
 * so it works in CI right after the Playwright run and locally without tsx.
 *
 *   node tests/stg-smoke/sweep/aggregate.mjs
 */
import { readdirSync, readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const RESULTS_DIR = join(here, '..', '..', '..', 'sweep-results')
const RECORDS_DIR = join(RESULTS_DIR, 'records')

/** Outcomes that represent a confirmed gap worth a bucket issue. */
const GAP_OUTCOMES = new Set([
  'load-error',
  'redirected-to-login',
  'landmark-missing',
  'empty-state',
])

function loadRecords() {
  if (!existsSync(RECORDS_DIR)) return []
  return readdirSync(RECORDS_DIR)
    .filter((f) => f.endsWith('.json'))
    .map((f) => JSON.parse(readFileSync(join(RECORDS_DIR, f), 'utf8')))
    .sort((a, b) => a.path.localeCompare(b.path))
}

function summarize(records) {
  const byOutcome = {}
  const byArea = {}
  for (const r of records) {
    byOutcome[r.outcome] = (byOutcome[r.outcome] ?? 0) + 1
    byArea[r.area] ??= { total: 0, gaps: 0 }
    byArea[r.area].total += 1
    if (GAP_OUTCOMES.has(r.outcome)) byArea[r.area].gaps += 1
  }
  return { total: records.length, byOutcome, byArea }
}

const OUTCOME_ICON = {
  ok: '✅',
  'ok-with-warnings': '⚠️',
  'redirected-to-login': '🔒',
  forbidden: '⛔',
  'landmark-missing': '❌',
  'load-error': '💥',
  'empty-state': '🕳️',
}

function toMarkdown(records, summary) {
  const lines = []
  lines.push('# Exploratory sweep catalog — isnad-graph (#969)')
  lines.push('')
  lines.push(`Generated: ${new Date().toISOString()}`)
  lines.push(`Routes exercised: **${summary.total}**`)
  lines.push('')
  lines.push('## Outcome summary')
  lines.push('')
  lines.push('| Outcome | Count |')
  lines.push('| --- | --- |')
  for (const [outcome, count] of Object.entries(summary.byOutcome).sort()) {
    lines.push(`| ${OUTCOME_ICON[outcome] ?? ''} ${outcome} | ${count} |`)
  }
  lines.push('')
  lines.push('## By area')
  lines.push('')
  lines.push('| Area | Routes | Gaps |')
  lines.push('| --- | --- | --- |')
  for (const [area, s] of Object.entries(summary.byArea).sort()) {
    lines.push(`| ${area} | ${s.total} | ${s.gaps} |`)
  }
  lines.push('')
  lines.push('## Per-route detail')
  lines.push('')
  lines.push('| Route | Area | Access | Outcome | Console | Net ≥400 | Empty-state |')
  lines.push('| --- | --- | --- | --- | --- | --- | --- |')
  for (const r of records) {
    const icon = OUTCOME_ICON[r.outcome] ?? ''
    lines.push(
      `| \`${r.path}\` (${r.label}) | ${r.area} | ${r.access} | ${icon} ${r.outcome} | ${r.consoleErrors.length} | ${r.networkErrors.length} | ${r.emptyStateText ? '`' + r.emptyStateText + '`' : '—'} |`,
    )
  }
  lines.push('')

  const gaps = records.filter((r) => GAP_OUTCOMES.has(r.outcome))
  if (gaps.length) {
    lines.push('## Candidate gaps (file as bucket issues)')
    lines.push('')
    for (const r of gaps) {
      lines.push(`### ${r.label} — \`${r.path}\` (${r.outcome})`)
      if (r.consoleErrors.length) {
        lines.push('- Console errors:')
        for (const e of r.consoleErrors.slice(0, 5)) lines.push(`  - \`${e}\``)
      }
      if (r.networkErrors.length) {
        lines.push('- Failing requests:')
        for (const n of r.networkErrors.slice(0, 5)) lines.push(`  - ${n.status} \`${n.url}\``)
      }
      if (r.emptyStateText) lines.push(`- Empty-state copy: \`${r.emptyStateText}\``)
      lines.push('')
    }
  } else {
    lines.push('_No load/redirect/landmark/empty-state gaps recorded in this run._')
    lines.push('')
  }
  return lines.join('\n')
}

function main() {
  const records = loadRecords()
  mkdirSync(RESULTS_DIR, { recursive: true })
  const summary = summarize(records)
  writeFileSync(
    join(RESULTS_DIR, 'sweep-catalog.json'),
    JSON.stringify({ generatedAt: new Date().toISOString(), summary, records }, null, 2),
  )
  writeFileSync(join(RESULTS_DIR, 'SWEEP-CATALOG.md'), toMarkdown(records, summary))
  if (records.length === 0) {
    console.warn(
      'sweep: no records found in sweep-results/records/ — run the sweep first (npm run e2e:sweep).',
    )
  } else {
    console.log(`sweep: aggregated ${records.length} route records → sweep-results/SWEEP-CATALOG.md`)
  }
}

main()
