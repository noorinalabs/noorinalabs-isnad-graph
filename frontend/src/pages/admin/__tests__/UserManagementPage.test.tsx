import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import UserManagementPage from '../UserManagementPage'
import {
  fetchAdminUsers,
  fetchAdminUser,
  fetchRoles,
  setUserRole,
} from '../../../api/admin-client'
import type { AdminUser, AdminUserList, Role } from '../../../api/admin-client'

vi.mock('../../../api/admin-client', () => ({
  fetchAdminUsers: vi.fn(),
  fetchAdminUser: vi.fn(),
  fetchRoles: vi.fn(),
  setUserRole: vi.fn(),
}))

// Partial-mock the auth hook so the panel can read the current user's id (for
// the self-demote guard) while keeping the real `deriveHighestRole` the page
// also imports from this module.
const mockUseAuth = vi.fn()
vi.mock('../../../hooks/useAuth', async (importActual) => {
  const actual = await importActual<typeof import('../../../hooks/useAuth')>()
  return { ...actual, useAuth: () => mockUseAuth() }
})

// Current operator id used by default — distinct from the `u1` fixture so the
// pre-existing role-change tests are NOT treated as self-edits.
const SELF_ID = 'admin-self'

// Role names kept as variables so the test survives any future vocab change.
const READER = 'reader'
const ADMIN = 'admin'

const CATALOG: Role[] = [
  { id: 'r-trial', name: 'trial', description: null, created_at: '2026-01-01T00:00:00Z' },
  { id: 'r-reader', name: READER, description: null, created_at: '2026-01-01T00:00:00Z' },
  { id: 'r-researcher', name: 'researcher', description: null, created_at: '2026-01-01T00:00:00Z' },
  { id: 'r-admin', name: ADMIN, description: null, created_at: '2026-01-01T00:00:00Z' },
]

function makeUser(over: Partial<AdminUser> = {}): AdminUser {
  return {
    id: 'u1',
    email: 'amina@example.com',
    display_name: 'Amina',
    email_verified: true,
    avatar_url: null,
    locale: 'en',
    is_active: true,
    created_at: '2026-02-01T00:00:00Z',
    roles: [READER],
    ...over,
  }
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <UserManagementPage />
    </QueryClientProvider>,
  )
}

describe('UserManagementPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchRoles).mockResolvedValue(CATALOG)
    mockUseAuth.mockReturnValue({ user: { id: SELF_ID } })
  })

  it('shows the loading state initially', () => {
    vi.mocked(fetchAdminUsers).mockImplementation(() => new Promise(() => {}))
    renderPage()
    expect(screen.getByText(/Loading/i)).toBeInTheDocument()
  })

  it('renders an error state when the list query fails', async () => {
    vi.mocked(fetchAdminUsers).mockRejectedValue(new Error('boom: users unreachable'))
    renderPage()
    await waitFor(() =>
      expect(screen.getByText(/Error: boom: users unreachable/)).toBeInTheDocument(),
    )
  })

  it('renders user rows with name, email, verified and status from user-service shape', async () => {
    const list: AdminUserList = { items: [makeUser()], next_cursor: null }
    vi.mocked(fetchAdminUsers).mockResolvedValue(list)
    renderPage()

    expect(await screen.findByText('Amina')).toBeInTheDocument()
    expect(screen.getByText('amina@example.com')).toBeInTheDocument()
    // scope to the cell — "Verified" is also the column header text
    expect(screen.getByRole('cell', { name: 'Verified' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Active' })).toBeInTheDocument()
  })

  it('falls back to email when display_name is null, and reflects inactive/unverified', async () => {
    const list: AdminUserList = {
      items: [makeUser({ display_name: null, email_verified: false, is_active: false })],
      next_cursor: null,
    }
    vi.mocked(fetchAdminUsers).mockResolvedValue(list)
    renderPage()

    // name cell falls back to the email
    expect(await screen.findByRole('button', { name: 'amina@example.com' })).toBeInTheDocument()
    expect(screen.getByText('Unverified')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('shows the highest current role in the select and calls setUserRole on change', async () => {
    const list: AdminUserList = { items: [makeUser({ roles: [READER] })], next_cursor: null }
    vi.mocked(fetchAdminUsers).mockResolvedValue(list)
    vi.mocked(setUserRole).mockResolvedValue(undefined)
    renderPage()

    const select = (await screen.findByLabelText('Role for Amina')) as HTMLSelectElement
    await waitFor(() => expect(select.value).toBe(READER))

    fireEvent.change(select, { target: { value: ADMIN } })

    await waitFor(() => expect(setUserRole).toHaveBeenCalledOnce())
    expect(setUserRole).toHaveBeenCalledWith('u1', ADMIN, [READER], CATALOG)
  })

  it('opens the detail modal and shows user-service fields', async () => {
    const list: AdminUserList = { items: [makeUser()], next_cursor: null }
    vi.mocked(fetchAdminUsers).mockResolvedValue(list)
    vi.mocked(fetchAdminUser).mockResolvedValue(makeUser({ roles: [READER, ADMIN] }))
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Amina' }))

    const heading = await screen.findByText('User Detail')
    const modal = heading.parentElement as HTMLElement
    expect(within(modal).getByText('reader, admin')).toBeInTheDocument()
    expect(within(modal).getByText('en')).toBeInTheDocument()
  })

  it('disables Previous on the first page and Next when there is no next_cursor', async () => {
    const list: AdminUserList = { items: [makeUser()], next_cursor: null }
    vi.mocked(fetchAdminUsers).mockResolvedValue(list)
    renderPage()

    await screen.findByText('Amina')
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('advances the cursor when Next is clicked', async () => {
    vi.mocked(fetchAdminUsers)
      .mockResolvedValueOnce({ items: [makeUser({ display_name: 'Page One' })], next_cursor: 'cur-2' })
      .mockResolvedValueOnce({ items: [makeUser({ display_name: 'Page Two' })], next_cursor: null })
    renderPage()

    await screen.findByText('Page One')
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await screen.findByText('Page Two')
    expect(vi.mocked(fetchAdminUsers).mock.calls[1]?.[0]).toBe('cur-2')
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled()
  })

  it('renders an empty-state message when there are no users', async () => {
    vi.mocked(fetchAdminUsers).mockResolvedValue({ items: [], next_cursor: null })
    renderPage()
    expect(await screen.findByText('No users found.')).toBeInTheDocument()
  })

  it('blocks an admin from removing admin from their OWN row and warns inline', async () => {
    // The current operator IS this row, currently an admin.
    mockUseAuth.mockReturnValue({ user: { id: SELF_ID } })
    const list: AdminUserList = {
      items: [makeUser({ id: SELF_ID, display_name: 'Me', roles: [ADMIN] })],
      next_cursor: null,
    }
    vi.mocked(fetchAdminUsers).mockResolvedValue(list)
    renderPage()

    const select = (await screen.findByLabelText('Role for Me')) as HTMLSelectElement
    await waitFor(() => expect(select.value).toBe(ADMIN))

    fireEvent.change(select, { target: { value: READER } })

    // Guard fires: no mutation, an inline alert, and the select stays on admin.
    expect(setUserRole).not.toHaveBeenCalled()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/lock yourself out/i)
    expect(select.value).toBe(ADMIN)
  })

  it('allows demoting a DIFFERENT admin (not a self-demote)', async () => {
    mockUseAuth.mockReturnValue({ user: { id: SELF_ID } })
    const list: AdminUserList = {
      items: [makeUser({ id: 'u2', display_name: 'Other', roles: [ADMIN] })],
      next_cursor: null,
    }
    vi.mocked(fetchAdminUsers).mockResolvedValue(list)
    vi.mocked(setUserRole).mockResolvedValue(undefined)
    renderPage()

    const select = (await screen.findByLabelText('Role for Other')) as HTMLSelectElement
    await waitFor(() => expect(select.value).toBe(ADMIN))

    fireEvent.change(select, { target: { value: READER } })

    await waitFor(() => expect(setUserRole).toHaveBeenCalledOnce())
    expect(setUserRole).toHaveBeenCalledWith('u2', READER, [ADMIN], CATALOG)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('surfaces a failed role-change mutation inline under the row', async () => {
    const list: AdminUserList = { items: [makeUser({ roles: [READER] })], next_cursor: null }
    vi.mocked(fetchAdminUsers).mockResolvedValue(list)
    vi.mocked(setUserRole).mockRejectedValue(new Error('assign failed: 409 conflict'))
    renderPage()

    const select = (await screen.findByLabelText('Role for Amina')) as HTMLSelectElement
    await waitFor(() => expect(select.value).toBe(READER))

    fireEvent.change(select, { target: { value: ADMIN } })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('assign failed: 409 conflict')
  })
})
