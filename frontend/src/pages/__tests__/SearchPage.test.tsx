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
