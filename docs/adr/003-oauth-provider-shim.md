# ADR-003: Abstract OAuth behind a common interface

## Status: Accepted (Phase 7)

## Context
The platform needs to support multiple OAuth providers (Google, GitHub, potentially others). Each provider has different token formats, scopes, and callback flows. Hardcoding provider-specific logic throughout the codebase would make adding new providers expensive.

## Decision
Create an abstract OAuth provider interface with provider-specific implementations behind it. The API layer interacts only with the abstract interface.

## Consequences
- Adding a new OAuth provider requires only a new implementation class
- Token validation, user info extraction, and session management are standardized
- Slightly more upfront design work than a single-provider implementation
- Testing can mock the interface rather than individual provider SDKs
