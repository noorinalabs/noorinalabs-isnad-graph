import { afterEach, describe, it, expect } from 'vitest'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import LanguageToggle from '../LanguageToggle'
import i18n from '../../i18n'
import { STORAGE_KEY } from '../../i18n/config'

afterEach(async () => {
  await act(async () => {
    await i18n.changeLanguage('en')
  })
  localStorage.clear()
})

describe('LanguageToggle', () => {
  it('opens the menu and lists all seven locales by native name', async () => {
    const user = userEvent.setup()
    render(<LanguageToggle />)

    await user.click(screen.getByRole('button', { name: /select language/i }))

    const menu = screen.getByRole('menu')
    const items = within(menu).getAllByRole('menuitemradio')
    expect(items).toHaveLength(7)
    expect(within(menu).getByText('العربية')).toBeInTheDocument()
    expect(within(menu).getByText('Türkçe')).toBeInTheDocument()
    expect(within(menu).getByText('English')).toBeInTheDocument()
  })

  it('switches the active locale and flips document dir for RTL', async () => {
    const user = userEvent.setup()
    render(<LanguageToggle />)

    await user.click(screen.getByRole('button', { name: /select language/i }))
    await user.click(screen.getByRole('menuitemradio', { name: /العربية/ }))

    await waitFor(() => expect(i18n.language).toBe('ar'))
    expect(document.documentElement.getAttribute('dir')).toBe('rtl')
    expect(document.documentElement.getAttribute('lang')).toBe('ar')
    expect(localStorage.getItem(STORAGE_KEY)).toBe('ar')

    // Menu closes after selecting.
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('returns to LTR when switching back to an LTR locale', async () => {
    const user = userEvent.setup()
    render(<LanguageToggle />)

    await i18n.changeLanguage('ar')
    expect(document.documentElement.getAttribute('dir')).toBe('rtl')

    await user.click(screen.getByRole('button', { name: /select language/i }))
    await user.click(screen.getByRole('menuitemradio', { name: /Türkçe/ }))

    await waitFor(() => expect(i18n.language).toBe('tr'))
    expect(document.documentElement.getAttribute('dir')).toBe('ltr')
  })

  it('marks the active locale as checked', async () => {
    const user = userEvent.setup()
    render(<LanguageToggle />)

    await user.click(screen.getByRole('button', { name: /select language/i }))
    const english = screen.getByRole('menuitemradio', { name: /English/ })
    expect(english).toHaveAttribute('aria-checked', 'true')
  })
})
