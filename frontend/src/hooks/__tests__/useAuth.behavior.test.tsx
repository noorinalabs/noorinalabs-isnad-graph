import { renderHook, waitFor, act } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import type { ReactNode } from "react"

import {
  AuthProvider,
  useAuth,
  emitSessionExpired,
  SESSION_EXPIRED_EVENT,
} from "../useAuth"
import type { AuthUser } from "../useAuth"

// AuthProvider drives real `fetch` (no API-client indirection), reads/writes
// localStorage + sessionStorage, and navigates via `window.location.href`.
// These tests stub all three so the provider's auth state machine can be
// exercised in jsdom without a backend.

function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: "6cf04f80-ede7-42e6-9756-43f8ce8f220d",
    email: "jane@example.com",
    display_name: "Jane Smith",
    avatar_url: null,
    email_verified: true,
    is_active: true,
    locale: null,
    created_at: "2026-04-20T03:09:36.076621Z",
    roles: [],
    ...overrides,
  }
}

function jsonResponse(status: number, body: unknown = {}): Response {
  // 204/304 are null-body statuses — the Response constructor rejects a body
  // for them. Everything else carries the JSON payload.
  const nullBody = status === 204 || status === 304
  return new Response(nullBody ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

/** Last entry of an array (Array.prototype.at isn't in the configured lib). */
function last<T>(arr: T[]): T {
  return arr[arr.length - 1]!
}

/** Render the provider and wait out the initial `loadUser` effect. */
async function renderAuth() {
  const view = renderHook(() => useAuth(), { wrapper })
  await waitFor(() => expect(view.result.current.loading).toBe(false))
  return view
}

let fetchMock: ReturnType<typeof vi.fn>
let locationHref: string

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()

  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)

  // `window.location.href = ...` is the provider's navigation primitive.
  // Replace location with a plain object so assignment is observable and
  // jsdom doesn't attempt a real (unimplemented) navigation.
  locationHref = "http://localhost/app"
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      get href() {
        return locationHref
      },
      set href(v: string) {
        locationHref = v
      },
      pathname: "/app",
      search: "",
    },
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("useAuth — context guard", () => {
  it("throws when used outside an AuthProvider", () => {
    // Suppress React's error-boundary console noise for this expected throw.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {})
    expect(() => renderHook(() => useAuth())).toThrow(
      /must be used within an AuthProvider/,
    )
    spy.mockRestore()
  })
})

describe("AuthProvider — initial load", () => {
  it("stays unauthenticated and does not call /me when no token is stored", async () => {
    const { result } = await renderAuth()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.user).toBeNull()
    expect(result.current.loading).toBe(false)
  })

  it("loads the user from /users/me when a valid token is present", async () => {
    localStorage.setItem("access_token", "valid-token")
    fetchMock.mockResolvedValueOnce(jsonResponse(200, makeUser()))

    const { result } = await renderAuth()

    expect(result.current.user?.email).toBe("jane@example.com")
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toContain("/api/v1/users/me")
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: "Bearer valid-token",
    })
  })

  it("refreshes the access token on a 401 and retries /me with the new token", async () => {
    localStorage.setItem("access_token", "stale-token")
    // 1) /me -> 401, 2) /auth/token/refresh -> 200 new token, 3) /me retry -> 200
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "fresh-token" }))
      .mockResolvedValueOnce(jsonResponse(200, makeUser({ email: "after@refresh.com" })))

    const { result } = await renderAuth()

    expect(result.current.user?.email).toBe("after@refresh.com")
    // The refreshed token is persisted for subsequent requests.
    expect(localStorage.getItem("access_token")).toBe("fresh-token")
    expect(fetchMock).toHaveBeenCalledTimes(3)
    const refreshCall = fetchMock.mock.calls[1]!
    expect(refreshCall[0]).toContain("/auth/token/refresh")
    expect((refreshCall[1] as RequestInit).method).toBe("POST")
  })

  it("clears auth when the token is expired and the refresh also fails", async () => {
    localStorage.setItem("access_token", "stale-token")
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "refresh rejected" }))

    const { result } = await renderAuth()

    expect(result.current.user).toBeNull()
    expect(localStorage.getItem("access_token")).toBeNull()
  })
})

describe("AuthProvider — role derivation", () => {
  it("exposes isAdmin/role/hasRole derived from the loaded user's roles", async () => {
    localStorage.setItem("access_token", "valid-token")
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, makeUser({ roles: ["editor", "admin"] })),
    )

    const { result } = await renderAuth()

    expect(result.current.isAdmin).toBe(true)
    expect(result.current.role).toBe("admin")
    expect(result.current.hasRole("moderator")).toBe(true)
  })

  it("defaults an unauthenticated session to the viewer role", async () => {
    const { result } = await renderAuth()

    expect(result.current.isAdmin).toBe(false)
    expect(result.current.role).toBe("viewer")
    expect(result.current.hasRole("editor")).toBe(false)
  })
})

describe("AuthProvider — session-expired event", () => {
  it("flips sessionExpired when the event fires for an authenticated user", async () => {
    localStorage.setItem("access_token", "valid-token")
    fetchMock.mockResolvedValueOnce(jsonResponse(200, makeUser()))
    const { result } = await renderAuth()

    expect(result.current.sessionExpired).toBe(false)
    act(() => emitSessionExpired())
    await waitFor(() => expect(result.current.sessionExpired).toBe(true))
  })

  it("ignores the event when no user was ever authenticated", async () => {
    const { result } = await renderAuth()

    act(() => {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
    })
    // No previously-authenticated user -> no re-auth modal.
    expect(result.current.sessionExpired).toBe(false)
  })

  it("dismissSessionExpired stores the return URL, clears auth, and routes to /login", async () => {
    localStorage.setItem("access_token", "valid-token")
    fetchMock.mockResolvedValueOnce(jsonResponse(200, makeUser()))
    const { result } = await renderAuth()

    act(() => result.current.dismissSessionExpired())

    expect(sessionStorage.getItem("oauth_return_url")).toBe("/app")
    expect(localStorage.getItem("access_token")).toBeNull()
    expect(result.current.user).toBeNull()
    expect(locationHref).toBe("/login")
  })
})

describe("AuthProvider — sign-out flows", () => {
  it("signOut revokes the current session, clears auth, and routes to /login", async () => {
    localStorage.setItem("access_token", "valid-token")
    // initial /me
    fetchMock.mockResolvedValueOnce(jsonResponse(200, makeUser()))
    const { result } = await renderAuth()

    // signOut: GET /sessions -> list, DELETE /sessions/{current}
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse(200, {
          sessions: [
            { id: "sess-1", is_current: false },
            { id: "sess-2", is_current: true },
          ],
        }),
      )
      .mockResolvedValueOnce(jsonResponse(204))

    await act(async () => {
      await result.current.signOut()
    })

    const deleteCall = last(fetchMock.mock.calls)
    expect(deleteCall[0]).toContain("/api/v1/sessions/sess-2")
    expect((deleteCall[1] as RequestInit).method).toBe("DELETE")
    expect(localStorage.getItem("access_token")).toBeNull()
    expect(result.current.user).toBeNull()
    expect(locationHref).toBe("/login")
  })

  it("signOut still clears local auth when the revoke request throws", async () => {
    localStorage.setItem("access_token", "valid-token")
    fetchMock.mockResolvedValueOnce(jsonResponse(200, makeUser()))
    const { result } = await renderAuth()

    // Network failure mid-revoke must not strand the user in a signed-in UI.
    fetchMock.mockRejectedValueOnce(new Error("network down"))

    await act(async () => {
      await result.current.signOut()
    })

    expect(localStorage.getItem("access_token")).toBeNull()
    expect(result.current.user).toBeNull()
    expect(locationHref).toBe("/login")
  })

  it("signOutAll issues a DELETE against the sessions collection", async () => {
    localStorage.setItem("access_token", "valid-token")
    fetchMock.mockResolvedValueOnce(jsonResponse(200, makeUser()))
    const { result } = await renderAuth()

    fetchMock.mockResolvedValueOnce(jsonResponse(204))

    await act(async () => {
      await result.current.signOutAll()
    })

    const call = last(fetchMock.mock.calls)
    expect(call[0]).toContain("/api/v1/sessions")
    expect((call[1] as RequestInit).method).toBe("DELETE")
    expect(result.current.user).toBeNull()
    expect(locationHref).toBe("/login")
  })
})

describe("AuthProvider — refreshUser", () => {
  it("re-fetches /me and updates the user on success", async () => {
    localStorage.setItem("access_token", "valid-token")
    fetchMock.mockResolvedValueOnce(jsonResponse(200, makeUser()))
    const { result } = await renderAuth()

    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, makeUser({ display_name: "Jane R. Smith" })),
    )

    await act(async () => {
      await result.current.refreshUser()
    })

    expect(result.current.user?.display_name).toBe("Jane R. Smith")
  })

  it("is a no-op when no token is stored", async () => {
    const { result } = await renderAuth()
    fetchMock.mockClear()

    await act(async () => {
      await result.current.refreshUser()
    })

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("leaves the existing user intact when the background refresh errors", async () => {
    localStorage.setItem("access_token", "valid-token")
    fetchMock.mockResolvedValueOnce(jsonResponse(200, makeUser()))
    const { result } = await renderAuth()

    fetchMock.mockRejectedValueOnce(new Error("network blip"))

    await act(async () => {
      await result.current.refreshUser()
    })

    // Background refresh failures are swallowed — the stale-but-valid user stays.
    expect(result.current.user?.email).toBe("jane@example.com")
  })
})

describe("AuthProvider — new-user onboarding flag", () => {
  it("picks up the is_new_user sessionStorage flag and consumes it", async () => {
    sessionStorage.setItem("is_new_user", "1")

    const { result } = await renderAuth()

    expect(result.current.isNewUser).toBe(true)
    // The flag is one-shot — cleared so a reload doesn't re-trigger onboarding.
    expect(sessionStorage.getItem("is_new_user")).toBeNull()
  })

  it("dismissOnboarding clears the isNewUser state", async () => {
    sessionStorage.setItem("is_new_user", "1")
    const { result } = await renderAuth()

    act(() => result.current.dismissOnboarding())
    expect(result.current.isNewUser).toBe(false)
  })
})
