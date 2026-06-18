// Canonical hadith-grade tokens (produced by the API's grade_normalized field)
// mapped to display labels and Tailwind colour classes. The raw scholar text is
// shown verbatim; these helpers drive the badge/bar colour and the filter labels.

// GRADE_LABELS has a single source of truth in the backend
// (src/utils/grades.py). The JSON below is generated from it by
// `scripts/emit_grade_vocab.py emit` and kept in sync by the grade-vocab-drift
// CI step + pre-commit hook (ig#1054) — do NOT hand-edit the generated file.
// The colour/bar helpers below stay here: they are presentation, not vocabulary.
import gradeLabels from './grade-vocab.generated.json'

export const GRADE_LABELS: Record<string, string> = gradeLabels

// The full canonical grade vocabulary, in display order. Drives the search
// page's grade facet so it can never silently drop a valid grade or drift out of
// sync with the colour/label maps (#1062). Derived from GRADE_LABELS so a new
// grade is added in exactly one place.
export const GRADE_TOKENS: string[] = Object.keys(GRADE_LABELS)

export function gradeLabel(token: string): string {
  return GRADE_LABELS[token] ?? token
}

// Badge background/text classes keyed on the normalized token.
export function gradeColor(token: string | null): string {
  switch (token) {
    case 'sahih':
    case 'hasan_sahih':
      return 'bg-sahih-bg text-sahih'
    case 'hasan':
      return 'bg-hasan-bg text-hasan'
    case 'daif':
      return 'bg-daif-bg text-daif'
    case 'mawdu':
      return 'bg-mawdu-bg text-mawdu'
    default:
      return ''
  }
}

// Solid bar colour for the grading strength indicator.
export function gradeBarColor(token: string | null): string {
  switch (token) {
    case 'sahih':
    case 'hasan_sahih':
      return 'bg-sahih'
    case 'hasan':
      return 'bg-hasan'
    case 'daif':
      return 'bg-warning'
    case 'mawdu':
      return 'bg-destructive'
    default:
      return 'bg-muted'
  }
}

// Relative fill width for the grading bar (sound grades read fuller).
export function gradeBarWidth(token: string | null): string {
  switch (token) {
    case 'sahih':
    case 'hasan_sahih':
      return '100%'
    case 'hasan':
      return '75%'
    default:
      return '40%'
  }
}
