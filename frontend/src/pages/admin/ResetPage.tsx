import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { resetStage, resetSource, resetFull, ResetError } from '../../api/admin-client'
import { useModalA11y } from '../../hooks/useModalA11y'
import type {
  ResetLevel,
  ResetResponse,
  ResetStage,
  ResetSummary,
} from '../../types/admin'

// Pipeline stages, ordered low→high; mirrors the ingest-platform reset CLI.
const STAGES: ResetStage[] = ['raw', 'dedup', 'enriched', 'normalized', 'staged']

// The exact token the /full guard requires. Kept as a named constant so the
// typed-confirmation gate and the real-run call can never drift apart.
const OBLITERATE = 'OBLITERATE'

// Describes a reset the admin is about to confirm. `dryRun` and `confirm` are
// closures over the already-collected inputs so the modal stays generic and
// the real-run call site is the ONLY place that can fire a destructive request.
interface PendingReset {
  level: ResetLevel
  title: string
  warning: string
  requireObliterate: boolean
  dryRun: () => Promise<ResetResponse>
  confirm: () => Promise<ResetResponse>
}

// Turns a snake_case / camelCase contract key into a human label,
// e.g. "would_delete" → "Would delete", "kafkaTopics" → "Kafka topics".
function humanizeKey(key: string): string {
  const spaced = key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .trim()
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

// Renders a single summary value readably: counts get thousands separators,
// booleans read as Yes/No, primitive arrays are comma-joined, and anything
// still structured falls back to indented JSON (the contract is loose, so an
// unexpected nested shape stays legible rather than breaking the page).
function formatValue(value: unknown): string {
  if (typeof value === 'number') return value.toLocaleString()
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (value === null || value === undefined) return '—'
  if (Array.isArray(value) && value.every((v) => typeof v !== 'object' || v === null)) {
    return value.length === 0 ? '—' : value.map((v) => formatValue(v)).join(', ')
  }
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

// The dry-run / executed summary. A plain-string blob is shown verbatim; an
// object blob is laid out as a readable label → value list instead of raw JSON.
function ResetSummaryView({ summary }: { summary: ResetSummary }) {
  const { t } = useTranslation()
  if (typeof summary === 'string') {
    return (
      <pre
        style={{
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontSize: 'var(--text-sm)',
          marginTop: 8,
        }}
      >
        {summary}
      </pre>
    )
  }

  const entries = Object.entries(summary)
  if (entries.length === 0) {
    return (
      <p className="small-muted" style={{ marginTop: 8 }}>
        {t('admin.reset.summaryNoChanges')}
      </p>
    )
  }

  return (
    <dl
      style={{
        display: 'grid',
        gridTemplateColumns: 'auto 1fr',
        gap: '4px 12px',
        margin: '8px 0 0',
        fontSize: 'var(--text-sm)',
      }}
    >
      {entries.map(([key, value]) => {
        const formatted = formatValue(value)
        const isBlock = formatted.includes('\n')
        return (
          <div key={key} style={{ display: 'contents' }}>
            <dt className="small-muted" style={{ fontWeight: 600 }}>
              {humanizeKey(key)}
            </dt>
            <dd style={{ margin: 0 }}>
              {isBlock ? (
                <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }}>
                  {formatted}
                </pre>
              ) : (
                formatted
              )}
            </dd>
          </div>
        )
      })}
    </dl>
  )
}

// Renders a reset response — used for both the dry-run preview and the
// executed result. The `audit_entry_path` is surfaced here (ig#970 AC: audit
// entry visible in the admin activity view).
function ResetResultPanel({ result }: { result: ResetResponse }) {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      style={{
        marginTop: 12,
        padding: 'var(--spacing-3)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
      }}
    >
      <p>
        <strong>
          {result.dry_run ? t('admin.reset.dryRunPreview') : t('admin.reset.resetExecuted')}
        </strong>
        {' — '}
        {t('admin.reset.resultLevel')} {result.level}
      </p>
      <p className="small-muted">
        {t('admin.reset.resultConfirmationMethod', { method: result.confirmation_method })}
      </p>
      <p className="small-muted">
        {t('admin.reset.resultAuditEntry')} <code>{result.audit_entry_path}</code>
      </p>
      <ResetSummaryView summary={result.summary} />
    </div>
  )
}

// The confirmation modal. Enforces the two-phase contract:
//   1. A dry-run preview MUST run (and succeed) before any real-run control
//      is even rendered.
//   2. For a full reset, the real-run button stays disabled until the admin
//      types OBLITERATE exactly. The token only travels on `confirm()`.
function ResetConfirmModal({
  pending,
  onClose,
}: {
  pending: PendingReset
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [preview, setPreview] = useState<ResetResponse | null>(null)
  const [executed, setExecuted] = useState<ResetResponse | null>(null)
  const [obliterate, setObliterate] = useState('')
  const [busy, setBusy] = useState<'idle' | 'preview' | 'confirm'>('idle')
  const [error, setError] = useState<string | null>(null)

  // Esc-to-close, focus trap, auto-focus on open, and focus restore on close.
  const dialogRef = useModalA11y(onClose)

  const runDryRun = async () => {
    setError(null)
    setBusy('preview')
    try {
      setPreview(await pending.dryRun())
    } catch (err) {
      setError(err instanceof ResetError ? err.message : String(err))
    } finally {
      setBusy('idle')
    }
  }

  const runConfirm = async () => {
    setError(null)
    setBusy('confirm')
    try {
      setExecuted(await pending.confirm())
    } catch (err) {
      setError(err instanceof ResetError ? err.message : String(err))
    } finally {
      setBusy('idle')
    }
  }

  // The OBLITERATE gate: for a full reset the real-run button is disabled
  // until the typed string matches exactly.
  const obliterateOk = !pending.requireObliterate || obliterate === OBLITERATE
  const confirmDisabled = busy !== 'idle' || !obliterateOk

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--spacing-4)',
        zIndex: 1000,
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="reset-modal-title"
        tabIndex={-1}
        style={{
          background: 'var(--color-background)',
          color: 'var(--color-foreground)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--spacing-5)',
          width: '100%',
          maxWidth: 560,
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
      >
        <h2 id="reset-modal-title">{pending.title}</h2>

        <div
          className="error-text"
          style={{
            border: '1px solid var(--color-destructive)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--spacing-3)',
            marginBottom: 'var(--spacing-3)',
          }}
        >
          {pending.warning}
        </div>

        {!executed && (
          <>
            {preview ? (
              <ResetResultPanel result={preview} />
            ) : (
              <p className="small-muted">{t('admin.reset.dryRunHint')}</p>
            )}

            {error && (
              <p className="error-text" role="alert">
                {error}
              </p>
            )}

            <div className="flex-row" style={{ gap: 8, marginTop: 12 }}>
              <button className="btn" onClick={runDryRun} disabled={busy !== 'idle'}>
                {busy === 'preview'
                  ? t('admin.reset.runningDryRun')
                  : preview
                    ? t('admin.reset.reRunDryRun')
                    : t('admin.reset.runDryRun')}
              </button>
            </div>

            {/* Real-run controls appear ONLY after a successful dry run. */}
            {preview && (
              <div style={{ marginTop: 16 }}>
                {pending.requireObliterate && (
                  <label style={{ display: 'block', marginBottom: 8 }}>
                    {t('admin.reset.obliterateLabelPre')}
                    <code>{OBLITERATE}</code>
                    {t('admin.reset.obliterateLabelPost')}
                    <input
                      className="form-input-block"
                      value={obliterate}
                      onChange={(e) => setObliterate(e.target.value)}
                      aria-label={t('admin.reset.obliterateInputAria', { token: OBLITERATE })}
                      autoComplete="off"
                      spellCheck={false}
                    />
                  </label>
                )}
                <button
                  className="btn-danger"
                  onClick={runConfirm}
                  disabled={confirmDisabled}
                >
                  {busy === 'confirm'
                    ? t('admin.reset.resetting')
                    : pending.requireObliterate
                      ? t('admin.reset.obliterateBtn')
                      : t('admin.reset.runResetReal')}
                </button>
              </div>
            )}
          </>
        )}

        {executed && <ResetResultPanel result={executed} />}

        <div style={{ marginTop: 16 }}>
          <button className="btn" onClick={onClose}>
            {executed ? t('admin.reset.close') : t('admin.reset.cancel')}
          </button>
        </div>
      </div>
    </div>
  )
}

// Builds the PendingReset descriptor for a stage reset. Split out so the copy
// pulls from i18next while the destructive call sites stay centralized.
function makeStageReset(stage: ResetStage, t: TFunction): PendingReset {
  return {
    level: 'stage',
    title: t('admin.reset.stageTitle', { stage }),
    warning: t('admin.reset.stageWarning', { stage }),
    requireObliterate: false,
    dryRun: () => resetStage(stage, true),
    confirm: () => resetStage(stage, false),
  }
}

function makeSourceReset(source: string, t: TFunction): PendingReset {
  return {
    level: 'source',
    title: t('admin.reset.sourceTitle', { source }),
    warning: t('admin.reset.sourceWarning', { source }),
    requireObliterate: false,
    dryRun: () => resetSource(source, true),
    confirm: () => resetSource(source, false),
  }
}

function makeFullReset(t: TFunction): PendingReset {
  return {
    level: 'full',
    title: t('admin.reset.fullTitle'),
    warning: t('admin.reset.fullWarning'),
    requireObliterate: true,
    // The token rides the dry-run too: ingest#73's FullResetRequest makes
    // `confirmation` a REQUIRED field under extra="forbid", so a token-less
    // {dry_run:true} is rejected 422 by Pydantic before the handler runs —
    // the preview would never render and the OBLITERATE gate would be
    // unreachable. This is safe: a dry-run is server-side-inert (it routes
    // through write_dry_run_audit and never constructs the resetter — the
    // lazy-factory guarantee), so the token causes no wipe. The UI-side
    // OBLITERATE gate still governs the REAL run below.
    dryRun: () => resetFull(OBLITERATE, true),
    confirm: () => resetFull(OBLITERATE, false),
  }
}

export default function ResetPage() {
  const { t } = useTranslation()
  const [stage, setStage] = useState<ResetStage>('raw')
  const [source, setSource] = useState('')
  const [pending, setPending] = useState<PendingReset | null>(null)

  const openStageReset = () => setPending(makeStageReset(stage, t))

  const trimmedSource = source.trim()
  const openSourceReset = () => setPending(makeSourceReset(trimmedSource, t))

  const openFullReset = () => setPending(makeFullReset(t))

  return (
    <div className="admin-page">
      <h1>{t('admin.reset.title')}</h1>
      <p className="small-muted">{t('admin.reset.intro')}</p>

      <section className="section-mb">
        <h2>{t('admin.reset.sectionResetStage')}</h2>
        <p className="small-muted">{t('admin.reset.resetStageDesc')}</p>
        <div className="flex-row" style={{ gap: 8 }}>
          <select
            className="form-input"
            value={stage}
            onChange={(e) => setStage(e.target.value as ResetStage)}
            aria-label={t('admin.reset.stageAriaLabel')}
          >
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button className="btn" onClick={openStageReset}>
            {t('admin.reset.btnResetStage')}
          </button>
        </div>
      </section>

      <section className="section-mb">
        <h2>{t('admin.reset.sectionResetSource')}</h2>
        <p className="small-muted">{t('admin.reset.resetSourceDesc')}</p>
        <div className="flex-row" style={{ gap: 8 }}>
          <input
            className="form-input"
            style={{ flex: 1 }}
            placeholder={t('admin.reset.sourcePlaceholder')}
            value={source}
            onChange={(e) => setSource(e.target.value)}
            aria-label={t('admin.reset.sourceAriaLabel')}
          />
          <button className="btn" onClick={openSourceReset} disabled={trimmedSource === ''}>
            {t('admin.reset.btnResetSource')}
          </button>
        </div>
      </section>

      <section
        className="section-mb"
        style={{
          border: '1px solid var(--color-destructive)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--spacing-4)',
        }}
      >
        <h2 className="text-danger">{t('admin.reset.dangerZoneTitle')}</h2>
        <p className="error-text">{t('admin.reset.dangerZoneDesc')}</p>
        <button className="btn-danger" onClick={openFullReset}>
          {t('admin.reset.btnFullReset')}
        </button>
      </section>

      {pending && (
        <ResetConfirmModal pending={pending} onClose={() => setPending(null)} />
      )}
    </div>
  )
}
