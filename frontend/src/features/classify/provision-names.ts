import type { Language } from '@/i18n'

/** The guideline documents a citation can come from, by the corpus's document key. */
const GUIDELINE_NAMES: Record<string, Record<Language, string>> = {
  'guide-prohibited': {
    en: 'Guidelines on prohibited practices',
    de: 'Leitlinien zu verbotenen Praktiken',
  },
  'guide-high-risk-annex-iii': {
    en: 'Guidelines on high-risk classification',
    de: 'Leitlinien zur Hochrisiko-Einstufung',
  },
  'guide-definition': {
    en: 'Guidelines on the AI system definition',
    de: 'Leitlinien zur Definition eines KI-Systems',
  },
  'guide-art50': {
    en: 'Guidelines on the Art. 50 transparency duties',
    de: 'Leitlinien zu den Transparenzpflichten nach Art. 50',
  },
}
const GUIDELINES_FALLBACK: Record<Language, string> = {
  en: 'Commission guidelines',
  de: 'Leitlinien der Kommission',
}
const PARAGRAPH: Record<Language, string> = { en: 'para.', de: 'Rn.' }
const EXAMPLE: Record<Language, string> = { en: 'example', de: 'Beispiel' }
const RECITAL: Record<Language, string> = { en: 'Recital', de: 'Erwägungsgrund' }

/** `art:26:11` → "Art. 26(11)" / "Art. 26 Abs. 11"; `art:5:1:c:i` → "Art. 5(1)(c)(i)" /
 *  "Art. 5 Abs. 1 Buchst. c Ziff. i" (localisation.md › German citation style). */
function articleName(parts: readonly string[], language: Language): string {
  const [article, paragraph, ...points] = parts
  if (paragraph === undefined) return `Art. ${article}`
  if (language === 'de') {
    const letters = ['Buchst.', 'Ziff.'] as const
    const tail = points.map((point, n) => ` ${letters[Math.min(n, 1)]} ${point}`).join('')
    return `Art. ${article} Abs. ${paragraph}${tail}`
  }
  return `Art. ${article}(${paragraph})${points.map((point) => `(${point})`).join('')}`
}

/** `annex:III:4:a` → "Annex III 4(a)" / "Anhang III Nr. 4 Buchst. a"; `annex:I:A:11` →
 *  "Annex I Section A point 11" / "Anhang I Abschnitt A Nr. 11". */
function annexName(parts: readonly string[], language: Language): string {
  const [annex, first, second] = parts
  if (annex === 'I' && first !== undefined && second !== undefined) {
    return language === 'de'
      ? `Anhang I Abschnitt ${first} Nr. ${second}`
      : `Annex I Section ${first} point ${second}`
  }
  const head = language === 'de' ? `Anhang ${annex}` : `Annex ${annex}`
  if (first === undefined) return head
  if (language === 'de') return `${head} Nr. ${first}${second ? ` Buchst. ${second}` : ''}`
  return `${head} ${first}${second ? `(${second})` : ''}`
}

/** `guide:guide-prohibited:para:173` → "Guidelines on prohibited practices, para. 173". */
function guidelineName(parts: readonly string[], language: Language): string {
  const [doc = '', kind, number] = parts
  const title = GUIDELINE_NAMES[doc]?.[language] ?? GUIDELINES_FALLBACK[language]
  if (number === undefined) return title
  return `${title}, ${kind === 'ex' ? EXAMPLE[language] : PARAGRAPH[language]} ${number}`
}

/**
 * How a screen names a provision the engine cites, in English or German. An id the app doesn't
 * know is shown as it is, never dropped.
 */
export function provisionName(provisionId: string, language: Language): string {
  const [kind, ...parts] = provisionId.split(':')
  if (parts.length === 0) return provisionId
  switch (kind) {
    case 'art':
      return articleName(parts, language)
    case 'annex':
      return annexName(parts, language)
    case 'recital':
      return `${RECITAL[language]} ${parts.join(':')}`
    case 'guide':
      return guidelineName(parts, language)
    default:
      return provisionId
  }
}

/** Whether an id names the Act itself (an article or an Annex point), not a recital or guidance. */
export function isLawProvision(provisionId: string): boolean {
  return provisionId.startsWith('art:') || provisionId.startsWith('annex:')
}

/** The plain-label key of an Annex III point (`annex:III:4:a` → "III_4_a"), for i18n's annexPoint. */
export function annexPointKey(provisionId: string): string | null {
  const [kind, annex, number, letter] = provisionId.split(':')
  if (kind !== 'annex' || annex !== 'III' || number === undefined) return null
  return letter ? `III_${number}_${letter}` : `III_${number}`
}
