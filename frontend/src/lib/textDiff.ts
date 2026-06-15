// Word-level diff for comparing two hadith texts (matn or isnad). Each token is
// classified as shared — part of the longest common subsequence of the two token
// streams — or unique to one side, so the comparison view can highlight where two
// parallel narrations agree and where they diverge. Works for both Latin and
// Arabic script (matching is Unicode-letter/number aware). (#1037)

export type DiffToken = {
  text: string
  shared: boolean
}

export type TokenDiff = {
  a: DiffToken[]
  b: DiffToken[]
  sharedCount: number
  // Shared tokens as a fraction of the longer side, in [0, 1]. A purely local
  // signal; the API-provided similarity_score is preferred when known.
  overlap: number
}

const NON_WORD = /[^\p{L}\p{N}]+/gu

// Normalize a token for matching only: lowercase + strip non-word characters so
// "Allah," and "allah" align. Display always uses the original token.
function normalize(token: string): string {
  return token.toLowerCase().replace(NON_WORD, '')
}

function tokenize(text: string): string[] {
  return text.split(/\s+/).filter(Boolean)
}

// Longest-common-subsequence alignment over normalized tokens. Tokens that
// normalize to empty (pure punctuation) never count as shared.
export function diffTokens(textA: string, textB: string): TokenDiff {
  const tokensA = tokenize(textA)
  const tokensB = tokenize(textB)
  const normA = tokensA.map(normalize)
  const normB = tokensB.map(normalize)

  const m = normA.length
  const n = normB.length

  // dp[i][j] = LCS length of normA[i:] and normB[j:]. Indices are loop-bounded,
  // so the non-null assertions below are safe (noUncheckedIndexedAccess).
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0))
  for (let i = m - 1; i >= 0; i--) {
    const row = dp[i]!
    const nextRow = dp[i + 1]!
    const ai = normA[i]!
    for (let j = n - 1; j >= 0; j--) {
      if (ai && ai === normB[j]) {
        row[j] = nextRow[j + 1]! + 1
      } else {
        row[j] = Math.max(nextRow[j]!, row[j + 1]!)
      }
    }
  }

  const sharedA = new Array<boolean>(m).fill(false)
  const sharedB = new Array<boolean>(n).fill(false)
  let i = 0
  let j = 0
  let sharedCount = 0
  while (i < m && j < n) {
    const ai = normA[i]!
    if (ai && ai === normB[j]) {
      sharedA[i] = true
      sharedB[j] = true
      sharedCount++
      i++
      j++
    } else if (dp[i + 1]![j]! >= dp[i]![j + 1]!) {
      i++
    } else {
      j++
    }
  }

  const longer = Math.max(m, n)
  return {
    a: tokensA.map((text, idx) => ({ text, shared: sharedA[idx]! })),
    b: tokensB.map((text, idx) => ({ text, shared: sharedB[idx]! })),
    sharedCount,
    overlap: longer === 0 ? 0 : sharedCount / longer,
  }
}
