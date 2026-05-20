import { describe, it, expect } from "vitest"

import { deriveHighestRole } from "../useAuth"

describe("deriveHighestRole", () => {
  it("returns 'admin' when roles contains 'admin'", () => {
    expect(deriveHighestRole(["admin"])).toBe("admin")
  })

  it("returns 'trial' (lowest tier) when roles is empty", () => {
    expect(deriveHighestRole([])).toBe("trial")
  })

  it("returns the highest tier when multiple backend roles are present", () => {
    // researcher (rank 2) beats reader (rank 1)
    expect(deriveHighestRole(["reader", "researcher"])).toBe("researcher")
    // admin (rank 3) beats everything
    expect(deriveHighestRole(["trial", "reader", "researcher", "admin"])).toBe(
      "admin",
    )
  })

  it("returns the highest backend role and ignores unknown names", () => {
    // Reconciled to backend vocabulary (#876): researcher/reader/trial are
    // now first-class — no longer silently degrade to a stand-in tier.
    expect(deriveHighestRole(["researcher", "reader", "trial"])).toBe(
      "researcher",
    )
  })

  it("ignores role names outside the backend vocabulary", () => {
    // Legacy / unknown role names (e.g. the pre-#876 frontend-invented
    // `viewer`/`editor`/`moderator`) are dropped; fall back to `trial`.
    expect(deriveHighestRole(["viewer", "editor", "moderator"])).toBe("trial")
  })

  it("picks the highest matching tier even when unknown roles are mixed in", () => {
    expect(deriveHighestRole(["editor", "admin"])).toBe("admin")
    expect(deriveHighestRole(["viewer", "reader"])).toBe("reader")
  })

  it("returns the single matching tier when only one known role is present", () => {
    expect(deriveHighestRole(["reader"])).toBe("reader")
    expect(deriveHighestRole(["researcher"])).toBe("researcher")
    expect(deriveHighestRole(["trial"])).toBe("trial")
  })
})

// isAdmin derivation mirrors what AuthProvider does inline:
//   const isAdmin = (user?.roles ?? []).includes('admin')
// These guard the contract: admin UI should light up iff 'admin' is present.
describe("isAdmin derivation (AuthProvider contract)", () => {
  const isAdminFrom = (roles: string[] | undefined): boolean =>
    (roles ?? []).includes("admin")

  it("is true when roles contains 'admin'", () => {
    expect(isAdminFrom(["admin"])).toBe(true)
  })

  it("is false when roles contains only non-admin roles", () => {
    expect(isAdminFrom(["reader"])).toBe(false)
    expect(isAdminFrom(["researcher", "reader", "trial"])).toBe(false)
  })

  it("is false when roles is empty or undefined", () => {
    expect(isAdminFrom([])).toBe(false)
    expect(isAdminFrom(undefined)).toBe(false)
  })

  it("is true when 'admin' appears alongside other roles", () => {
    expect(isAdminFrom(["reader", "admin"])).toBe(true)
  })
})
