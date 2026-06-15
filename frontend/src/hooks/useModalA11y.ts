import { useEffect, useRef } from 'react'

// Elements that can receive keyboard focus inside a modal. Disabled controls
// and `tabindex="-1"` are excluded so the trap mirrors the browser's own
// tab order.
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

/**
 * Wires the three keyboard-accessibility behaviours a modal dialog needs:
 *
 *   - **Auto-focus** — moves focus to the first focusable control on open
 *     (falling back to the container itself if the modal has none yet).
 *   - **Focus trap** — Tab / Shift+Tab wrap within the modal instead of
 *     escaping to the page behind the overlay.
 *   - **Esc-to-close** — calls `onClose` when Escape is pressed.
 *   - **Focus restore** — returns focus to whatever was focused before the
 *     modal opened (the trigger) when the modal unmounts.
 *
 * Apply the returned ref to the dialog container and give that container
 * `tabIndex={-1}` so the container-focus fallback works.
 *
 * The modal is expected to be conditionally mounted/unmounted (as ResetPage
 * mounts it), so setup runs once on mount and restore runs on unmount. `onClose`
 * is read through a ref to keep that effect from re-running — and re-stealing
 * focus — on every parent render.
 */
export function useModalA11y(onClose: () => void) {
  const containerRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)

  // Keep the close callback current without re-running the setup effect below
  // (which would re-steal focus on every parent render).
  useEffect(() => {
    onCloseRef.current = onClose
  })

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // Remember the trigger so focus can return to it when the modal closes.
    const previouslyFocused = document.activeElement as HTMLElement | null

    const focusables = () =>
      Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))

    // Auto-focus the primary control (first focusable) on open.
    const initial = focusables()[0]
    if (initial) initial.focus()
    else container.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return

      const items = focusables()
      const first = items[0]
      const last = items[items.length - 1]
      if (!first || !last) {
        // Nothing tabbable yet — keep focus pinned to the container.
        event.preventDefault()
        return
      }
      const active = document.activeElement

      // Wrap at the boundaries (and reel focus back in if it has drifted
      // outside the container entirely).
      if (event.shiftKey) {
        if (active === first || !container.contains(active)) {
          event.preventDefault()
          last.focus()
        }
      } else if (active === last || !container.contains(active)) {
        event.preventDefault()
        first.focus()
      }
    }

    container.addEventListener('keydown', onKeyDown)
    return () => {
      container.removeEventListener('keydown', onKeyDown)
      previouslyFocused?.focus?.()
    }
  }, [])

  return containerRef
}
