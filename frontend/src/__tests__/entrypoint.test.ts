import { describe, expect, it } from 'vitest'

// Import the actual source files as raw strings via Vite's ?raw suffix so
// the test runs against the committed text without needing @types/node.
import entrypointSrc from '../../entrypoint.sh?raw'
import templateSrc from '../../runtime-config.js.template?raw'

/**
 * Guards the envsubst allowlist in entrypoint.sh against template drift (#1008).
 *
 * Root cause: runtime-config.js.template added ${INGEST_PLATFORM_ORIGIN} but the
 * envsubst allowlist was '${USER_SERVICE_ORIGIN}' only, so the placeholder shipped
 * verbatim. This test catches the whole class by asserting that every ${VAR}
 * reference in the template is present in the allowlist.
 */

/** Extract bare var names from every ${UPPER_CASE_VAR} occurrence in a string. */
function extractVarRefs(text: string): string[] {
  return [...text.matchAll(/\$\{([A-Z][A-Z0-9_]*)\}/g)]
    .map((m) => m[1])
    .filter((v): v is string => v !== undefined)
}

describe('entrypoint.sh — envsubst allowlist covers all template vars (#1008)', () => {
  it('template vars ⊆ allowlist (no placeholder can ship as a literal)', () => {
    const templateVars = extractVarRefs(templateSrc)
    expect(templateVars.length, 'template should reference at least one variable').toBeGreaterThan(0)

    // Extract the single-quoted allowlist argument: envsubst '${VAR1}${VAR2}' < "$TEMPLATE" > "$OUTPUT"
    const allowlistMatch = entrypointSrc.match(/envsubst\s+'([^']+)'/)
    expect(
      allowlistMatch,
      'entrypoint.sh must contain an envsubst call with a single-quoted allowlist',
    ).toBeTruthy()
    const allowlistVars = extractVarRefs(allowlistMatch![1] ?? '')

    const missing = templateVars.filter((v) => !allowlistVars.includes(v))
    expect(
      missing,
      `Template var(s) [${missing.join(', ')}] referenced in runtime-config.js.template ` +
        `are absent from the envsubst allowlist in entrypoint.sh. ` +
        `Add them to prevent the placeholder from shipping as a literal.`,
    ).toHaveLength(0)
  })

  it('allowlist contains USER_SERVICE_ORIGIN', () => {
    const allowlistMatch = entrypointSrc.match(/envsubst\s+'([^']+)'/)
    expect(allowlistMatch).toBeTruthy()
    expect(allowlistMatch![1]).toContain('${USER_SERVICE_ORIGIN}')
  })

  it('allowlist contains INGEST_PLATFORM_ORIGIN', () => {
    const allowlistMatch = entrypointSrc.match(/envsubst\s+'([^']+)'/)
    expect(allowlistMatch).toBeTruthy()
    expect(allowlistMatch![1]).toContain('${INGEST_PLATFORM_ORIGIN}')
  })

  it('fail-fast guard is present after the envsubst call', () => {
    // After substitution, entrypoint.sh must grep for residual '${' and exit 1.
    // This prevents a missing-allowlist-entry from silently shipping a malformed config.
    expect(entrypointSrc).toMatch(/grep.*\$\{/)
    expect(entrypointSrc).toMatch(/exit 1/)
  })
})
