import "@testing-library/jest-dom/vitest"

// Initialise the i18n singleton so components that call `useTranslation()`
// resolve real strings under test instead of raw keys.
import "../i18n"
