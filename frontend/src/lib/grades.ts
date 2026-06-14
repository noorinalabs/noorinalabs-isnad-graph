// Canonical hadith-grade tokens (produced by the API's grade_normalized field)
// mapped to display labels and Tailwind colour classes. The raw scholar text is
// shown verbatim; these helpers drive the badge/bar colour and the filter labels.

export const GRADE_LABELS: Record<string, string> = {
  sahih: 'Sahih',
  hasan: 'Hasan',
  hasan_sahih: 'Hasan Sahih',
  daif: "Da'if",
  mawdu: "Mawdu'",
  munkar: 'Munkar',
  shadh: 'Shadh',
}

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
