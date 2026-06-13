/**
 * Authentication setup project for the stg smoke harness (#968).
 *
 * Performs a PROGRAMMATIC email/password login against the live user-service
 * (`POST {USER_SERVICE_URL}/auth/login/email` — the same endpoint the real
 * LoginPage posts to) and persists a Playwright storage-state with the issued
 * JWT seeded into the frontend origin's localStorage under `access_token` —
 * which is exactly where `src/api/client.ts` and `ProtectedRoute` read it from.
 *
 * The storage-state is then reused by every `*.auth.spec.ts` (the `smoke-auth`
 * project depends on this `setup` project), so each spec starts already logged
 * in without re-hitting the auth endpoint.
 *
 * Credential-less contexts (e.g. a manual run without secrets exported): we
 * write an EMPTY storage-state so the dependent project still loads, and the
 * authenticated specs self-skip via `requireAuth()`.
 */
import { test as setup, expect, request } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import {
  BASE_URL,
  USER_SERVICE_URL,
  TEST_EMAIL,
  TEST_PASSWORD,
  hasAuthCreds,
  STORAGE_STATE,
} from './env'

const EMPTY_STATE = JSON.stringify({ cookies: [], origins: [] })

setup('authenticate', async () => {
  mkdirSync(dirname(STORAGE_STATE), { recursive: true })

  if (!hasAuthCreds) {
    // No creds in this environment — write an empty state so the dependent
    // project can still load; `*.auth.spec.ts` self-skip via requireAuth().
    writeFileSync(STORAGE_STATE, EMPTY_STATE)
    setup.skip(true, 'stg creds not configured (STG_TEST_EMAIL / STG_TEST_PASSWORD) — auth leg skipped')
    return
  }

  const api = await request.newContext({ baseURL: USER_SERVICE_URL })
  const res = await api.post('/auth/login/email', {
    data: { email: TEST_EMAIL, password: TEST_PASSWORD },
  })

  expect(
    res.ok(),
    `login/email failed: ${res.status()} ${res.statusText()} — check test-user creds and ${USER_SERVICE_URL}`,
  ).toBeTruthy()

  const body = (await res.json()) as { access_token?: string }
  expect(body.access_token, 'login response missing access_token').toBeTruthy()
  await api.dispose()

  // Seed the JWT into the frontend origin's localStorage — matches how the
  // real app stores it (LoginPage → localStorage.setItem('access_token', …)).
  const state = {
    cookies: [],
    origins: [
      {
        origin: new URL(BASE_URL).origin,
        localStorage: [{ name: 'access_token', value: body.access_token as string }],
      },
    ],
  }
  writeFileSync(STORAGE_STATE, JSON.stringify(state, null, 2))
})
