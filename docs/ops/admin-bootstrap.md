# Admin Bootstrap

The platform requires at least one admin user to access the admin dashboard
(user management, moderation, health, analytics, config). Since the dashboard
itself is gated behind `is_admin`, bootstrapping the first admin is a
chicken-and-egg problem that must be solved out-of-band.

Two mechanisms are provided:

## Option 1: CLI promotion (recommended for existing deployments)

Promote any registered user to admin by email:

```bash
isnad admin promote user@example.com
```

This connects to Neo4j, finds the `USER` node matching the given email, and
sets `is_admin = true`. The command exits with code 1 if no matching user is
found.

**Prerequisites:** the user must have logged in at least once via OAuth so that
a `USER` node exists in the graph.

## Option 2: First-user-is-admin (recommended for fresh deployments)

Set the environment variable before starting the API:

```bash
AUTH_FIRST_USER_IS_ADMIN=true
```

When enabled, the OAuth callback checks whether any `USER` nodes exist in
Neo4j. If the graph is empty (zero users), the first user to complete the
OAuth flow is automatically promoted to admin.

Once the first admin exists, subsequent users are created with the default
`is_admin = false` regardless of this setting.

**Security note:** disable this variable (`AUTH_FIRST_USER_IS_ADMIN=false` or
remove it) after the first admin has been created, especially in production.

## Verifying admin access

After promotion, the user should:

1. Log out and log back in (to get a fresh JWT reflecting the updated claims).
2. Navigate to the admin dashboard -- the admin link should appear in the
   sidebar.
3. Confirm access to user management, health, and config pages.
