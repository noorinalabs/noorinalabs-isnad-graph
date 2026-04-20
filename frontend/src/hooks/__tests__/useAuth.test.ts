import { describe, it, expect } from "vitest"

import { deriveHighestRole } from "../useAuth"

describe("deriveHighestRole", () => {
  it("returns 'admin' when roles contains 'admin'", () => {
    expect(deriveHighestRole(["admin"])).toBe("admin")
  })

  it("returns 'viewer' when roles is empty", () => {
    expect(deriveHighestRole([])).toBe("viewer")
  })

  it("returns the highest tier when multiple frontend-known roles are present", () => {
    // moderator (rank 2) beats editor (rank 1)
    expect(deriveHighestRole(["editor", "moderator"])).toBe("moderator")
    // admin (rank 3) beats everything
    expect(deriveHighestRole(["viewer", "editor", "moderator", "admin"])).toBe(
      "admin",
    )
  })

  it("ignores backend role names that are not in the UserRole union", () => {
    // user-service DB roles `researcher`, `reader`, `trial` aren't in
    // the frontend UserRole union yet — they should be skipped.
    expect(deriveHighestRole(["researcher", "reader", "trial"])).toBe("viewer")
  })

  it("picks the highest matching tier even when unknown roles are mixed in", () => {
    expect(deriveHighestRole(["researcher", "admin"])).toBe("admin")
    expect(deriveHighestRole(["reader", "editor"])).toBe("editor")
  })

  it("returns the single matching tier when only one known role is present", () => {
    expect(deriveHighestRole(["editor"])).toBe("editor")
    expect(deriveHighestRole(["moderator"])).toBe("moderator")
    expect(deriveHighestRole(["viewer"])).toBe("viewer")
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
