import { render, screen } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"

import WelcomeBanner from "../WelcomeBanner"
import type { AuthUser } from "../../hooks/useAuth"

// Mock useAuth — the banner pulls user/isNewUser/dismissOnboarding from context.
const mockUseAuth = vi.fn()
vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}))

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

describe("WelcomeBanner", () => {
  beforeEach(() => {
    mockUseAuth.mockReset()
  })

  it("greets the user by first name when display_name is set", () => {
    mockUseAuth.mockReturnValue({
      user: makeUser({ display_name: "Jane Smith" }),
      isNewUser: true,
      dismissOnboarding: vi.fn(),
    })

    render(<WelcomeBanner />)

    expect(
      screen.getByText("Welcome to Isnad Graph, Jane!"),
    ).toBeInTheDocument()
  })

  it("falls back to email local-part when display_name is null (does NOT crash)", () => {
    mockUseAuth.mockReturnValue({
      user: makeUser({ display_name: null, email: "jane@example.com" }),
      isNewUser: true,
      dismissOnboarding: vi.fn(),
    })

    // Regression guard for #825: `user.name.split(...)` used to throw
    // `TypeError: can't access property "split", e.name is undefined`.
    expect(() => render(<WelcomeBanner />)).not.toThrow()
    expect(
      screen.getByText("Welcome to Isnad Graph, jane!"),
    ).toBeInTheDocument()
  })

  it("renders nothing when user is not new", () => {
    mockUseAuth.mockReturnValue({
      user: makeUser(),
      isNewUser: false,
      dismissOnboarding: vi.fn(),
    })

    const { container } = render(<WelcomeBanner />)
    expect(container).toBeEmptyDOMElement()
  })

  it("renders nothing when user is null (unauthenticated)", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isNewUser: true,
      dismissOnboarding: vi.fn(),
    })

    const { container } = render(<WelcomeBanner />)
    expect(container).toBeEmptyDOMElement()
  })
})
