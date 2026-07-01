import { render, screen } from '@testing-library/react'
import { describe, it, expect, afterEach, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import i18n from '../../../i18n'
import ar from '../../../i18n/locales/ar.json'
import en from '../../../i18n/locales/en.json'
import AuditLogPage from '../AuditLogPage'
import SystemHealthPage from '../SystemHealthPage'

// The pages fire admin-client queries on mount; resolve them with empty-but-
// shaped payloads so the only thing under test is the statically-rendered,
// translated chrome (and the queries settle inside act(), no test warnings).
vi.mock('../../../api/admin-client', () => ({
  fetchAuditLogs: vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, limit: 20 })),
  fetchSystemHealth: vi.fn(() =>
    Promise.resolve({ status: 'ok', neo4j: true, postgres: true, redis: true }),
  ),
}))

// The admin/* page bodies were routed through i18next in ig#1104. These tests
// assert the wiring end-to-end: an admin page's static body text renders from
// the active locale bundle (Arabic here) rather than the previous hardcoded
// English — i.e. flipping the locale flips the rendered copy.

function renderPage(node: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{node}</QueryClientProvider>)
}

afterEach(async () => {
  await i18n.changeLanguage('en')
})

describe('admin pages route body copy through i18next (ig#1104)', () => {
  it('AuditLogPage heading renders the English bundle string under en', async () => {
    await i18n.changeLanguage('en')
    renderPage(<AuditLogPage />)
    expect(await screen.findByRole('heading', { name: en.admin.auditLog.title })).toBeInTheDocument()
  })

  it('AuditLogPage heading renders the Arabic bundle string under ar', async () => {
    await i18n.changeLanguage('ar')
    renderPage(<AuditLogPage />)
    // Translated (not the English "Audit Log").
    expect(await screen.findByRole('heading', { name: ar.admin.auditLog.title })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: en.admin.auditLog.title })).toBeNull()
  })

  it('SystemHealthPage heading resolves keys (no raw admin.* leak)', async () => {
    await i18n.changeLanguage('ar')
    renderPage(<SystemHealthPage />)
    const heading = await screen.findByRole('heading', { name: ar.admin.systemHealth.title })
    expect(heading).toBeInTheDocument()
    // A resolved key never renders its raw dotted path.
    expect(heading.textContent).not.toMatch(/admin\./)
  })
})
