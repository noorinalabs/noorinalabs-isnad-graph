import { beforeAll, describe, expect, it, vi } from 'vitest'
import { dataViz, dataVizDark } from '@noorinalabs/design-system'

// ForceGraph.tsx reads `window.matchMedia` at module load (REDUCED_MOTION). jsdom
// doesn't implement it, so stub before the dynamic import below. We import the
// module dynamically (after the stub) rather than statically so the stub is in
// place when the module body executes.
let communityColor: (typeof import('../ForceGraph'))['communityColor']

beforeAll(async () => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  )
  ;({ communityColor } = await import('../ForceGraph'))
})

describe('communityColor', () => {
  it('derives the palette from the DS data-viz tokens (no bespoke hardcoded hex)', () => {
    // Each community id maps to the matching DS categorical token, not a local
    // hex constant — this is the core #979 contract.
    for (let i = 0; i < dataViz.categorical.length; i++) {
      expect(communityColor(i)).toBe(dataViz.categorical[i])
    }
  })

  it('cycles by modulo for ids beyond the palette length', () => {
    const len = dataViz.categorical.length
    expect(communityColor(len)).toBe(dataViz.categorical[0])
    expect(communityColor(len + 3)).toBe(dataViz.categorical[3])
  })

  it('uses the supplied (theme-reactive) palette when one is passed', () => {
    // The canvas renderer passes themeColors.community, which is dataVizDark in
    // dark mode — so the same community id resolves to the dark token.
    expect(communityColor(2, dataVizDark.categorical)).toBe(dataVizDark.categorical[2])
    expect(communityColor(0, dataVizDark.categorical)).not.toBe(communityColor(0))
  })

  it('returns a neutral fallback for a null/undefined community', () => {
    expect(communityColor(null)).toBe('#999')
    expect(communityColor(undefined)).toBe('#999')
  })
})
