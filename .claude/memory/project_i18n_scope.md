---
name: project_i18n_scope
description: Internationalization is UI/navigation only — source API data stays untransformed
type: project
promotion_target: none
status: active
---

i18n (#650) scope: **UI chrome and navigation only**, not source data.

- Site language and navigation should be toggleable (Turkish, Indonesian, Malay, Arabic, Bosnian, Urdu)
- Original source data from the API (hadith text, narrator names, etc.) stays untransformed
- No translation of scholarly content at this stage

**Why:** Steven wants the platform to be navigable in multiple languages but the scholarly data should remain authentic/original.

**How to apply:** When implementing #650, translate only UI strings (labels, buttons, navigation, headings, help text). API responses are passed through as-is. Use a standard i18n framework (react-i18next or similar) with JSON translation files per locale.
