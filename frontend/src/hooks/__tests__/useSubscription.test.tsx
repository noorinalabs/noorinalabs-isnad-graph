import { renderHook, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"

import { useSubscription } from "../useSubscription"

vi.mock("../../api/client", () => ({
  fetchSubscriptionOrNull: vi.fn(),
}))

vi.mock("../useAuth", () => ({
  useAuth: vi.fn(),
}))

import { fetchSubscriptionOrNull } from "../../api/client"
import { useAuth } from "../useAuth"

const mockFetch = fetchSubscriptionOrNull as ReturnType<typeof vi.fn>
const mockUseAuth = useAuth as ReturnType<typeof vi.fn>

function wrapper({ children }: { children: ReactNode }) {
  // New client per test so queries don't share cache between cases.
  // Match app defaults (retry: 1) to prove the hook's own retry:false wins.
  const client = new QueryClient({
    defaultOptions: { queries: { retry: 1 } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

function authAs(opts: { user: unknown; isAdmin: boolean }) {
  mockUseAuth.mockReturnValue({
    user: opts.user,
    loading: false,
    isAdmin: opts.isAdmin,
    role: opts.isAdmin ? "admin" : "viewer",
    hasRole: () => opts.isAdmin,
    sessionExpired: false,
    isNewUser: false,
    logout: vi.fn(),
    signOut: vi.fn(),
    signOutAll: vi.fn(),
    dismissSessionExpired: vi.fn(),
    dismissOnboarding: vi.fn(),
    refreshUser: vi.fn(),
  })
}

describe("useSubscription", () => {
  beforeEach(() => {
    mockFetch.mockReset()
    mockUseAuth.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("does not fetch when user is admin (bypass — admins have no subscription)", async () => {
    authAs({ user: { id: "u1", email: "a@b.c" }, isAdmin: true })

    const { result } = renderHook(() => useSubscription(), { wrapper })

    // Let any pending microtasks flush — the query must stay disabled.
    await new Promise((resolve) => setTimeout(resolve, 10))

    expect(mockFetch).not.toHaveBeenCalled()
    expect(result.current.subscription).toBeNull()
    expect(result.current.isLoading).toBe(false)
  })

  it("does not fetch when no user is authenticated", async () => {
    authAs({ user: null, isAdmin: false })

    renderHook(() => useSubscription(), { wrapper })
    await new Promise((resolve) => setTimeout(resolve, 10))

    expect(mockFetch).not.toHaveBeenCalled()
  })

  it("fetches for non-admin authenticated users", async () => {
    authAs({ user: { id: "u1", email: "a@b.c" }, isAdmin: false })
    mockFetch.mockResolvedValue({
      tier: "trial",
      status: "trial",
      days_remaining: 5,
      trial_start: "2026-01-01",
      trial_expires: "2026-01-15",
    })

    const { result } = renderHook(() => useSubscription(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(mockFetch).toHaveBeenCalledTimes(1)
    expect(result.current.isTrial).toBe(true)
    expect(result.current.daysRemaining).toBe(5)
  })

  it("treats a 404 (no subscription) as null without retrying", async () => {
    authAs({ user: { id: "u1", email: "a@b.c" }, isAdmin: false })
    // The fetch helper resolves null on 404 — the hook must surface that as
    // `subscription: null` (terminal state, no retry storm).
    mockFetch.mockResolvedValue(null)

    const { result } = renderHook(() => useSubscription(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(mockFetch).toHaveBeenCalledTimes(1)
    expect(result.current.subscription).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it("does not retry on a 500 error (proves retry:false applies to real errors too)", async () => {
    authAs({ user: { id: "u1", email: "a@b.c" }, isAdmin: false })
    mockFetch.mockRejectedValue(new Error("API error: 500 Internal Server Error"))

    const { result } = renderHook(() => useSubscription(), { wrapper })

    await waitFor(() => expect(result.current.error).toBeTruthy())
    // retry:false on the hook overrides the global retry:1 default — exactly
    // one call, and the error surfaces rather than being swallowed.
    expect(mockFetch).toHaveBeenCalledTimes(1)
    expect(result.current.subscription).toBeNull()
  })
})
