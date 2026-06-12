import { useState } from 'react'
import { resetStage, resetSource, resetFull, ResetError } from '../../api/admin-client'
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

function formatSummary(summary: ResetSummary): string {
  return typeof summary === 'string' ? summary : JSON.stringify(summary, null, 2)
}

// Renders a reset response — used for both the dry-run preview and the
// executed result. The `audit_entry_path` is surfaced here (ig#970 AC: audit
// entry visible in the admin activity view).
function ResetResultPanel({ result }: { result: ResetResponse }) {
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
        <strong>{result.dry_run ? 'Dry-run preview' : 'Reset executed'}</strong>
        {' — level: '}
        {result.level}
      </p>
      <p className="small-muted">Confirmation method: {result.confirmation_method}</p>
      <p className="small-muted">
        Audit entry: <code>{result.audit_entry_path}</code>
      </p>
      <pre
        style={{
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontSize: 'var(--text-sm)',
          marginTop: 8,
        }}
      >
        {formatSummary(result.summary)}
      </pre>
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
  const [preview, setPreview] = useState<ResetResponse | null>(null)
  const [executed, setExecuted] = useState<ResetResponse | null>(null)
  const [obliterate, setObliterate] = useState('')
  const [busy, setBusy] = useState<'idle' | 'preview' | 'confirm'>('idle')
  const [error, setError] = useState<string | null>(null)

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
        role="dialog"
        aria-modal="true"
        aria-labelledby="reset-modal-title"
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
              <p className="small-muted">
                Start with a dry run — it validates the request and writes an audit
                entry but touches no infrastructure.
              </p>
            )}

            {error && (
              <p className="error-text" role="alert">
                {error}
              </p>
            )}

            <div className="flex-row" style={{ gap: 8, marginTop: 12 }}>
              <button className="btn" onClick={runDryRun} disabled={busy !== 'idle'}>
                {busy === 'preview'
                  ? 'Running dry run…'
                  : preview
                    ? 'Re-run dry run'
                    : 'Run dry-run preview'}
              </button>
            </div>

            {/* Real-run controls appear ONLY after a successful dry run. */}
            {preview && (
              <div style={{ marginTop: 16 }}>
                {pending.requireObliterate && (
                  <label style={{ display: 'block', marginBottom: 8 }}>
                    Type <code>{OBLITERATE}</code> to enable the real reset:
                    <input
                      className="form-input-block"
                      value={obliterate}
                      onChange={(e) => setObliterate(e.target.value)}
                      aria-label="Type OBLITERATE to confirm"
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
                    ? 'Resetting…'
                    : pending.requireObliterate
                      ? 'Obliterate everything'
                      : 'Run reset for real'}
                </button>
              </div>
            )}
          </>
        )}

        {executed && <ResetResultPanel result={executed} />}

        <div style={{ marginTop: 16 }}>
          <button className="btn" onClick={onClose}>
            {executed ? 'Close' : 'Cancel'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ResetPage() {
  const [stage, setStage] = useState<ResetStage>('raw')
  const [source, setSource] = useState('')
  const [pending, setPending] = useState<PendingReset | null>(null)

  const openStageReset = () =>
    setPending({
      level: 'stage',
      title: `Reset stage: ${stage}`,
      warning: `This clears all pipeline artifacts at the "${stage}" stage. Downstream stages may need to be re-run.`,
      requireObliterate: false,
      dryRun: () => resetStage(stage, true),
      confirm: () => resetStage(stage, false),
    })

  const trimmedSource = source.trim()
  const openSourceReset = () =>
    setPending({
      level: 'source',
      title: `Reset source: ${trimmedSource}`,
      warning: `This removes all data ingested from source "${trimmedSource}" across every pipeline stage.`,
      requireObliterate: false,
      dryRun: () => resetSource(trimmedSource, true),
      confirm: () => resetSource(trimmedSource, false),
    })

  const openFullReset = () =>
    setPending({
      level: 'full',
      title: 'Full reset — obliterate the entire pipeline',
      warning:
        'This permanently wipes MinIO, Backblaze B2, Kafka topics, the Neo4j graph, and PostgreSQL. Every ingested hadith, narrator, and chain is destroyed. There is no undo.',
      requireObliterate: true,
      dryRun: () => resetFull('', true),
      confirm: () => resetFull(OBLITERATE, false),
    })

  return (
    <div className="admin-page">
      <h1>Pipeline Reset</h1>
      <p className="small-muted">
        Trigger ingest-platform pipeline resets. Every action previews as a dry
        run first; nothing is destroyed until you explicitly confirm.
      </p>

      <section className="section-mb">
        <h2>Reset a stage</h2>
        <p className="small-muted">Clear artifacts at a single pipeline stage.</p>
        <div className="flex-row" style={{ gap: 8 }}>
          <select
            className="form-input"
            value={stage}
            onChange={(e) => setStage(e.target.value as ResetStage)}
            aria-label="Stage to reset"
          >
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button className="btn" onClick={openStageReset}>
            Reset stage…
          </button>
        </div>
      </section>

      <section className="section-mb">
        <h2>Reset a source</h2>
        <p className="small-muted">Remove everything ingested from one source.</p>
        <div className="flex-row" style={{ gap: 8 }}>
          <input
            className="form-input"
            style={{ flex: 1 }}
            placeholder="source id (e.g. sunnah)"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            aria-label="Source to reset"
          />
          <button className="btn" onClick={openSourceReset} disabled={trimmedSource === ''}>
            Reset source…
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
        <h2 className="text-danger">Danger zone — full reset</h2>
        <p className="error-text">
          Obliterates the entire pipeline: MinIO, Backblaze B2, Kafka, Neo4j, and
          PostgreSQL. Irreversible.
        </p>
        <button className="btn-danger" onClick={openFullReset}>
          Full reset / OBLITERATE…
        </button>
      </section>

      {pending && (
        <ResetConfirmModal pending={pending} onClose={() => setPending(null)} />
      )}
    </div>
  )
}
