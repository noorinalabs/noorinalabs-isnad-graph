import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { RelevanceBadge } from '../SearchPage'

describe('RelevanceBadge (ig#1065)', () => {
  it('renders 100% for a score above 1.0, not 130%', () => {
    render(<RelevanceBadge score={1.3} />)
    expect(screen.getByText('100%')).toBeTruthy()
  })

  it('renders 0% for a negative score, not a negative percentage', () => {
    render(<RelevanceBadge score={-0.2} />)
    expect(screen.getByText('0%')).toBeTruthy()
  })

  it('renders the exact percentage for in-range scores', () => {
    render(<RelevanceBadge score={0.75} />)
    expect(screen.getByText('75%')).toBeTruthy()
  })

  it('renders 100% for a score of exactly 1.0', () => {
    render(<RelevanceBadge score={1.0} />)
    expect(screen.getByText('100%')).toBeTruthy()
  })

  it('renders 0% for a score of exactly 0', () => {
    render(<RelevanceBadge score={0} />)
    expect(screen.getByText('0%')).toBeTruthy()
  })
})

describe('RelevanceBadge absolute-confidence thresholds (ig#1070)', () => {
  // Under the saturating API transform the badge colour reads as absolute
  // confidence, so a weak top hit is muted rather than promoted to sahih green.
  it('colours a strong score (>=0.9) as sahih', () => {
    const { container } = render(<RelevanceBadge score={0.92} />)
    expect(container.querySelector('.text-sahih')).toBeTruthy()
  })

  it('colours a mid score (>=0.7) as warning', () => {
    const { container } = render(<RelevanceBadge score={0.75} />)
    expect(container.querySelector('.text-warning')).toBeTruthy()
  })

  it('colours a weak score (<0.7) as muted, not sahih', () => {
    const { container } = render(<RelevanceBadge score={0.3} />)
    expect(container.querySelector('.text-muted-foreground')).toBeTruthy()
    expect(container.querySelector('.text-sahih')).toBeNull()
  })
})
