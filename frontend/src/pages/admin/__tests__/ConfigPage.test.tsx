import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import ConfigPage from '../ConfigPage'

const CONFIG = {
  rate_limit_per_minute: 60,
  cors_origins: ['http://localhost:3000'],
  feature_flags: {},
  max_search_results: 100,
  max_pagination_limit: 100,
  log_retention_days: 7,
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ConfigPage />
    </QueryClientProvider>,
  )
}

describe('ConfigPage — log retention (ig#1038)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the log-retention control populated from config', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ ...CONFIG, entries: [], total: 0 }))),
    )
    renderPage()

    await screen.findByText('Log Retention')
    const input = screen.getByLabelText(/Keep last N days/i) as HTMLInputElement
    expect(input.value).toBe('7')
  })

  it('PATCHes the changed log_retention_days value on save', async () => {
    const fetchMock = vi.fn((_url: string | URL | Request, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (method === 'PATCH') {
        return Promise.resolve(jsonResponse({ ...CONFIG, log_retention_days: 30 }))
      }
      return Promise.resolve(jsonResponse({ ...CONFIG, entries: [], total: 0 }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPage()

    const input = (await screen.findByLabelText(/Keep last N days/i)) as HTMLInputElement
    fireEvent.change(input, { target: { value: '30' } })
    fireEvent.click(screen.getByText('Save Configuration'))

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === 'PATCH',
      )
      expect(patchCall).toBeTruthy()
      expect(JSON.parse((patchCall![1] as RequestInit).body as string)).toEqual({
        log_retention_days: 30,
      })
    })
  })
})
