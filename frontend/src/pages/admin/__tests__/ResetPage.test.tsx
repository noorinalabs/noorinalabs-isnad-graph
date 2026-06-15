import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ResetPage from '../ResetPage'
import { resetStage, resetFull, ResetError } from '../../../api/admin-client'
import type { ResetResponse } from '../../../types/admin'

// Mock the cross-service reset client. ResetError stays a real class so the
// page's `err instanceof ResetError` branch behaves as in production.
vi.mock('../../../api/admin-client', () => {
  class ResetError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.name = 'ResetError'
      this.status = status
    }
  }
  return {
    resetStage: vi.fn(),
    resetSource: vi.fn(),
    resetFull: vi.fn(),
    ResetError,
  }
})

function makeResponse(over: Partial<ResetResponse>): ResetResponse {
  return {
    level: 'stage',
    dry_run: true,
    confirmation_method: 'dry_run',
    audit_entry_path: '/audit/reset-2026.json',
    summary: { would_delete: 42 },
    ...over,
  }
}

describe('ResetPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the three reset affordances and the danger-zone warning', () => {
    render(<ResetPage />)
    expect(screen.getByRole('heading', { name: 'Pipeline Reset' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Reset a stage' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Reset a source' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Danger zone/i })).toBeInTheDocument()
    expect(screen.getByText(/Irreversible/)).toBeInTheDocument()
  })

  it('disables the source reset button until a source is entered', async () => {
    const user = userEvent.setup()
    render(<ResetPage />)
    const btn = screen.getByRole('button', { name: 'Reset source…' })
    expect(btn).toBeDisabled()
    await user.type(screen.getByLabelText('Source to reset'), 'sunnah')
    expect(btn).toBeEnabled()
  })

  it('runs a dry run first, then the real stage reset only on explicit confirm', async () => {
    const user = userEvent.setup()
    vi.mocked(resetStage)
      .mockResolvedValueOnce(makeResponse({ level: 'stage', dry_run: true }))
      .mockResolvedValueOnce(
        makeResponse({ level: 'stage', dry_run: false, confirmation_method: 'explicit' }),
      )
    render(<ResetPage />)

    await user.click(screen.getByRole('button', { name: 'Reset stage…' }))
    // Modal open; no real-run control is rendered before the dry run.
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Run reset for real' }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Run dry-run preview' }))
    expect(resetStage).toHaveBeenNthCalledWith(1, 'raw', true)
    await screen.findByText(/Dry-run preview/)
    // Audit entry surfaced (AC).
    expect(screen.getByText('/audit/reset-2026.json')).toBeInTheDocument()

    const realBtn = await screen.findByRole('button', { name: 'Run reset for real' })
    await user.click(realBtn)
    expect(resetStage).toHaveBeenNthCalledWith(2, 'raw', false)
    await screen.findByText(/Reset executed/)
  })

  it('keeps the OBLITERATE button disabled until the exact word is typed', async () => {
    const user = userEvent.setup()
    vi.mocked(resetFull)
      .mockResolvedValueOnce(
        makeResponse({ level: 'full', dry_run: true, confirmation_method: 'typed_token' }),
      )
      .mockResolvedValueOnce(
        makeResponse({ level: 'full', dry_run: false, confirmation_method: 'typed_token' }),
      )
    render(<ResetPage />)

    await user.click(screen.getByRole('button', { name: 'Full reset / OBLITERATE…' }))
    await user.click(screen.getByRole('button', { name: 'Run dry-run preview' }))

    // Dry run carries the OBLITERATE token (ingest#73 requires `confirmation`
    // even on dry-run) but with dry_run:true — server-side-inert, no wipe.
    expect(resetFull).toHaveBeenNthCalledWith(1, 'OBLITERATE', true)
    await screen.findByText(/Dry-run preview/)

    const obliterateBtn = screen.getByRole('button', { name: 'Obliterate everything' })
    expect(obliterateBtn).toBeDisabled()

    const input = screen.getByLabelText('Type OBLITERATE to confirm')
    await user.type(input, 'obliterate') // wrong case
    expect(obliterateBtn).toBeDisabled()

    await user.clear(input)
    await user.type(input, 'OBLITERATE')
    expect(obliterateBtn).toBeEnabled()

    // No real-run call fired while the gate was closed.
    expect(resetFull).toHaveBeenCalledTimes(1)
    expect(resetFull).not.toHaveBeenCalledWith(expect.anything(), false)

    await user.click(obliterateBtn)
    // The real run sends the OBLITERATE token with dry_run:false.
    expect(resetFull).toHaveBeenNthCalledWith(2, 'OBLITERATE', false)
    await screen.findByText(/Reset executed/)
  })

  it('does not render any real-run control before a successful dry run', async () => {
    const user = userEvent.setup()
    render(<ResetPage />)
    await user.click(screen.getByRole('button', { name: 'Full reset / OBLITERATE…' }))
    expect(
      screen.queryByRole('button', { name: 'Obliterate everything' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Type OBLITERATE to confirm')).not.toBeInTheDocument()
    // resetFull is untouched — nothing fires merely from opening the modal.
    expect(resetFull).not.toHaveBeenCalled()
  })

  it('surfaces a distinct error message when the reset endpoint fails', async () => {
    const user = userEvent.setup()
    vi.mocked(resetStage).mockRejectedValueOnce(
      new ResetError(503, 'Service unavailable: the auth key service (JWKS) is unreachable. Try again shortly.'),
    )
    render(<ResetPage />)

    await user.click(screen.getByRole('button', { name: 'Reset stage…' }))
    await user.click(screen.getByRole('button', { name: 'Run dry-run preview' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/JWKS\) is unreachable/)
    })
    // A failed dry run never exposes a real-run control.
    expect(
      screen.queryByRole('button', { name: 'Run reset for real' }),
    ).not.toBeInTheDocument()
  })

  it('cancels and closes the modal without firing any reset', async () => {
    const user = userEvent.setup()
    render(<ResetPage />)
    await user.click(screen.getByRole('button', { name: 'Reset stage…' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(resetStage).not.toHaveBeenCalled()
  })
})

describe('ResetPage — modal accessibility (#987)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('auto-focuses the primary control when the modal opens', async () => {
    const user = userEvent.setup()
    render(<ResetPage />)
    await user.click(screen.getByRole('button', { name: 'Reset stage…' }))
    expect(screen.getByRole('button', { name: 'Run dry-run preview' })).toHaveFocus()
  })

  it('closes on Escape and restores focus to the trigger', async () => {
    const user = userEvent.setup()
    render(<ResetPage />)
    const trigger = screen.getByRole('button', { name: 'Reset stage…' })
    await user.click(trigger)
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    // Focus returns to the control that opened the modal.
    expect(trigger).toHaveFocus()
  })

  it('traps Tab focus inside the dialog (forward wrap)', async () => {
    const user = userEvent.setup()
    render(<ResetPage />)
    await user.click(screen.getByRole('button', { name: 'Reset stage…' }))

    const dryRun = screen.getByRole('button', { name: 'Run dry-run preview' })
    const cancel = screen.getByRole('button', { name: 'Cancel' })
    expect(dryRun).toHaveFocus()

    await user.tab()
    expect(cancel).toHaveFocus()
    // Tabbing past the last control wraps back to the first.
    await user.tab()
    expect(dryRun).toHaveFocus()
  })

  it('traps Shift+Tab focus inside the dialog (backward wrap)', async () => {
    const user = userEvent.setup()
    render(<ResetPage />)
    await user.click(screen.getByRole('button', { name: 'Reset stage…' }))

    const dryRun = screen.getByRole('button', { name: 'Run dry-run preview' })
    const cancel = screen.getByRole('button', { name: 'Cancel' })
    expect(dryRun).toHaveFocus()

    // Shift+Tabbing back from the first control wraps to the last.
    await user.tab({ shift: true })
    expect(cancel).toHaveFocus()
  })

  it('renders an object dry-run summary as a readable list, not raw JSON', async () => {
    const user = userEvent.setup()
    vi.mocked(resetStage).mockResolvedValueOnce(
      makeResponse({
        level: 'stage',
        dry_run: true,
        summary: { would_delete: 1234, kafka_topics: ['raw', 'dedup'] },
      }),
    )
    render(<ResetPage />)
    await user.click(screen.getByRole('button', { name: 'Reset stage…' }))
    await user.click(screen.getByRole('button', { name: 'Run dry-run preview' }))
    await screen.findByText(/Dry-run preview/)

    // Humanized labels instead of raw snake_case keys.
    expect(screen.getByText('Would delete')).toBeInTheDocument()
    expect(screen.getByText('Kafka topics')).toBeInTheDocument()
    // Count is formatted (locale-tolerant) and the array is comma-joined.
    expect(
      screen.getByText((content) => content.replace(/[,\s]/g, '') === '1234'),
    ).toBeInTheDocument()
    expect(screen.getByText('raw, dedup')).toBeInTheDocument()
    // The preview is not dumped as a raw JSON blob.
    expect(screen.queryByText(/"would_delete"/)).not.toBeInTheDocument()
  })
})
