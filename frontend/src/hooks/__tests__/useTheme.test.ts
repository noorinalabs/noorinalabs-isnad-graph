import { renderHook, act } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

import { useTheme } from "../useTheme"

const STORAGE_KEY = "isnad-graph-theme"

// jsdom does not implement matchMedia. We install a controllable stub so the
// tests can drive the `(prefers-color-scheme: dark)` query and fire `change`
// events at the hook's listener.
type MQListener = (e: MediaQueryListEvent) => void

function installMatchMedia(initialDark: boolean) {
  let matches = initialDark
  const listeners = new Set<MQListener>()

  const mql = {
    get matches() {
      return matches
    },
    media: "(prefers-color-scheme: dark)",
    addEventListener: (_: string, cb: MQListener) => listeners.add(cb),
    removeEventListener: (_: string, cb: MQListener) => listeners.delete(cb),
  }

  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => mql),
  )

  return {
    /** Flip the system preference and notify subscribers, as a real OS would. */
    setSystemDark(next: boolean) {
      matches = next
      for (const cb of listeners) {
        cb({ matches } as MediaQueryListEvent)
      }
    },
    get listenerCount() {
      return listeners.size
    },
  }
}

function dataTheme(): string | null {
  return document.documentElement.getAttribute("data-theme")
}

describe("useTheme", () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute("data-theme")
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("defaults to 'system' when nothing is stored, resolving to the OS preference", () => {
    installMatchMedia(true)

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe("system")
    expect(result.current.resolvedTheme).toBe("dark")
    // Mount effect applies the resolved theme to the document element.
    expect(dataTheme()).toBe("dark")
  })

  it("hydrates an explicit stored theme over the system default", () => {
    installMatchMedia(true)
    localStorage.setItem(STORAGE_KEY, "light")

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe("light")
    // Explicit 'light' wins even though the OS prefers dark.
    expect(result.current.resolvedTheme).toBe("light")
    expect(dataTheme()).toBe("light")
  })

  it("ignores a corrupt stored value and falls back to 'system'", () => {
    installMatchMedia(false)
    localStorage.setItem(STORAGE_KEY, "neon-banana")

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe("system")
  })

  it("setTheme persists the choice and applies it to the document", () => {
    installMatchMedia(false)
    const { result } = renderHook(() => useTheme())

    act(() => result.current.setTheme("dark"))

    expect(result.current.theme).toBe("dark")
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark")
    expect(dataTheme()).toBe("dark")
  })

  it("toggle flips light <-> dark for explicit themes", () => {
    installMatchMedia(false)
    const { result } = renderHook(() => useTheme())

    act(() => result.current.setTheme("light"))
    act(() => result.current.toggle())
    expect(result.current.theme).toBe("dark")

    act(() => result.current.toggle())
    expect(result.current.theme).toBe("light")
  })

  it("toggle from 'system' resolves against the OS preference and lands on the opposite explicit theme", () => {
    // OS prefers dark -> toggling from 'system' should go to 'light'.
    installMatchMedia(true)
    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe("system")
    act(() => result.current.toggle())
    expect(result.current.theme).toBe("light")
  })

  it("re-applies the resolved theme when the OS preference changes while on 'system'", () => {
    const mm = installMatchMedia(false)
    const { result } = renderHook(() => useTheme())

    expect(result.current.resolvedTheme).toBe("light")
    expect(dataTheme()).toBe("light")

    // OS flips to dark — the 'system' listener should re-apply.
    act(() => mm.setSystemDark(true))
    expect(dataTheme()).toBe("dark")
  })

  it("does not subscribe to OS changes when an explicit theme is selected", () => {
    const mm = installMatchMedia(false)
    const { result } = renderHook(() => useTheme())

    act(() => result.current.setTheme("light"))
    // Explicit theme -> the effect's cleanup removed the 'system' listener.
    expect(mm.listenerCount).toBe(0)

    // An OS flip must not move an explicitly-pinned theme.
    act(() => mm.setSystemDark(true))
    expect(dataTheme()).toBe("light")
  })

  it("removes its OS-change listener on unmount", () => {
    const mm = installMatchMedia(false)
    const { unmount } = renderHook(() => useTheme())

    expect(mm.listenerCount).toBe(1)
    unmount()
    expect(mm.listenerCount).toBe(0)
  })
})
