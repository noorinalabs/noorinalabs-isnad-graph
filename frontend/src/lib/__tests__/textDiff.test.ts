import { describe, it, expect } from "vitest"
import { diffTokens } from "../textDiff"

describe("diffTokens", () => {
  it("marks every token shared for identical text", () => {
    const d = diffTokens("Actions are by intentions", "Actions are by intentions")
    expect(d.a.every((t) => t.shared)).toBe(true)
    expect(d.b.every((t) => t.shared)).toBe(true)
    expect(d.sharedCount).toBe(4)
    expect(d.overlap).toBe(1)
  })

  it("marks nothing shared for disjoint text", () => {
    const d = diffTokens("alpha beta gamma", "delta epsilon")
    expect(d.a.some((t) => t.shared)).toBe(false)
    expect(d.b.some((t) => t.shared)).toBe(false)
    expect(d.sharedCount).toBe(0)
    expect(d.overlap).toBe(0)
  })

  it("identifies the shared subsequence and the divergent tokens", () => {
    const d = diffTokens(
      "the prophet said actions are by intention",
      "the messenger said deeds are by intention",
    )
    // "the", "said", "are", "by", "intention" align as the common subsequence.
    const sharedA = d.a.filter((t) => t.shared).map((t) => t.text)
    expect(sharedA).toEqual(["the", "said", "are", "by", "intention"])
    const divergentA = d.a.filter((t) => !t.shared).map((t) => t.text)
    expect(divergentA).toEqual(["prophet", "actions"])
    expect(d.sharedCount).toBe(5)
  })

  it("matches case-insensitively and ignores surrounding punctuation", () => {
    const d = diffTokens("Allah, the Most Merciful.", "allah the most merciful")
    expect(d.a.every((t) => t.shared)).toBe(true)
    expect(d.sharedCount).toBe(4)
  })

  it("never treats pure punctuation as a shared token", () => {
    const d = diffTokens("peace -- be", "war -- gone")
    const shared = d.a.filter((t) => t.shared)
    expect(shared).toHaveLength(0)
  })

  it("handles Arabic script tokens", () => {
    const d = diffTokens("إنما الأعمال بالنيات", "إنما الأعمال بالنية")
    const sharedA = d.a.filter((t) => t.shared).map((t) => t.text)
    expect(sharedA).toEqual(["إنما", "الأعمال"])
    expect(d.sharedCount).toBe(2)
  })

  it("is empty-input safe", () => {
    const d = diffTokens("", "")
    expect(d.a).toEqual([])
    expect(d.b).toEqual([])
    expect(d.overlap).toBe(0)
  })
})
