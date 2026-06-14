import { describe, it, expect } from 'vitest'
import { gradeLabel, gradeColor, gradeBarColor, gradeBarWidth } from '../grades'

describe('grade helpers', () => {
  it('maps canonical tokens to display labels', () => {
    expect(gradeLabel('sahih')).toBe('Sahih')
    expect(gradeLabel('hasan_sahih')).toBe('Hasan Sahih')
    expect(gradeLabel('daif')).toBe("Da'if")
    expect(gradeLabel('mawdu')).toBe("Mawdu'")
  })

  it('falls back to the raw token for unknown values', () => {
    expect(gradeLabel('mysterious')).toBe('mysterious')
  })

  it('colours sahih and hasan_sahih as authentic', () => {
    expect(gradeColor('sahih')).toContain('text-sahih')
    expect(gradeColor('hasan_sahih')).toContain('text-sahih')
    expect(gradeBarColor('sahih')).toBe('bg-sahih')
    expect(gradeBarColor('hasan_sahih')).toBe('bg-sahih')
  })

  it('colours weak and fabricated grades distinctly', () => {
    expect(gradeColor('daif')).toContain('text-daif')
    expect(gradeBarColor('daif')).toBe('bg-warning')
    expect(gradeBarColor('mawdu')).toBe('bg-destructive')
  })

  it('returns neutral classes for null/unknown tokens', () => {
    expect(gradeColor(null)).toBe('')
    expect(gradeColor('munkar')).toBe('')
    expect(gradeBarColor(null)).toBe('bg-muted')
  })

  it('scales the bar width by soundness', () => {
    expect(gradeBarWidth('sahih')).toBe('100%')
    expect(gradeBarWidth('hasan_sahih')).toBe('100%')
    expect(gradeBarWidth('hasan')).toBe('75%')
    expect(gradeBarWidth('daif')).toBe('40%')
    expect(gradeBarWidth(null)).toBe('40%')
  })
})
