// The in-browser personal-data check under the description field (decision 026, item 15). It only
// warns: nothing is blocked, and the text never leaves the browser for this check. A pattern
// that misses is acceptable; one that fires on ordinary descriptions would teach users to ignore
// it, so each kind is matched narrowly.

/** What the check looks for, in the order the notice lists them. */
export const PERSONAL_DATA_KINDS = ['email', 'phone', 'iban', 'name'] as const
export type PersonalDataKind = (typeof PERSONAL_DATA_KINDS)[number]

const EMAIL = /[\p{L}\p{N}._%+-]+@[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)*\.\p{L}{2,}/gu

// Two letters and two check digits, then the account in groups of four (spaced or not) and a
// shorter last group. The checksum decides; the length is checked there too.
const IBAN_CANDIDATE =
  /(?<![\p{L}\p{N}])[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?(?![\p{L}\p{N}])/giu
const IBAN_MIN_LENGTH = 15
const IBAN_MAX_LENGTH = 34
const IBAN_MODULUS = 97n

// An international number (+49 …, 0049 …) or a national one starting with 0 (030 …, 0170/…),
// grouped by spaces, slashes, hyphens or brackets; or the North American 555-123-4567 form.
const PHONE_CANDIDATE =
  /(?:\+\d|(?<![\p{L}\p{N}.,])0\d)[\d ()/-]{5,24}\d|(?<![\p{L}\p{N}])\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?![\p{L}\p{N}])/gu
const PHONE_MIN_DIGITS = 7
// E.164 allows at most 15 digits.
const PHONE_MAX_DIGITS = 15
// 01/10/2026 and 07-10-2026 are dates, and +1 000 000 is an amount, not a number to call.
const DATE_LIKE = /^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$/
const THOUSANDS_GROUPED = /^\+?\d{1,3}(?: \d{3})+$/

// A courtesy title, or a common first name, before a capitalised word. German capitalises every
// noun, so a title after an article ("die Frau Mitte 30") is a noun, not a name.
const ARTICLE_BEFORE =
  '(?<!(?<![\\p{L}])(?:[Dd](?:er|ie|as|en|em|es)|[Ee]in(?:e|er|em|en|es)?|[Jj]ede[r]?|[Kk]eine|[Tt]he|[Aa]n?)\\s+)'
const TITLES = '(?:Mr|Mrs|Ms|Mx|Miss|Dr|Prof|Herr|Herrn|Frau)\\.?'
const SURNAME = "\\p{Lu}[\\p{Ll}\\p{Lu}'-]+"
const TITLE_AND_NAME = new RegExp(
  `${ARTICLE_BEFORE}(?<![\\p{L}\\p{N}])${TITLES}\\s+${SURNAME}`,
  'u',
)

// Common English and German first names. Left out on purpose: names that are also ordinary
// capitalised words (Will, Mark, Grant, Bill, Frank, May, June, Art, Christian, Adam …).
const FIRST_NAMES = [
  'Alexander Alice Amelia Andrea Andreas Anna Anja Anne Benjamin Birgit Charlotte',
  'Christina Claudia Daniel David Emily Emma Felix Finn Florian Gabriele Hannah Heike Ingrid',
  'Isabella Jacob James Jan Jennifer Jessica Johanna John Jonas Julia Jürgen Karin Katharina',
  'Klaus Laura Lea Leon Lisa Lukas Maria Markus Martin Mary Matthias Melanie Mia Michael Michaela',
  'Monika Noah Oliver Olivia Paul Peter Petra Robert Sabine Sandra Sarah Sebastian Sophia Sophie',
  'Stefan Stefanie Susanne Thomas Tobias Ursula William Wolfgang',
]
  .join(' ')
  .split(' ')
const FIRST_AND_LAST_NAME = new RegExp(
  `(?<![\\p{L}\\p{N}])(?:${FIRST_NAMES.join('|')})\\s+${SURNAME}`,
  'u',
)

function compact(text: string): string {
  return text.replace(/\s/g, '').toUpperCase()
}

/** ISO 13616: move the first four characters to the end, letters to 10–35, and the number mod 97
 *  is 1. Ruling out everything else keeps product codes and order numbers from firing. */
function isValidIban(candidate: string): boolean {
  const iban = compact(candidate)
  if (iban.length < IBAN_MIN_LENGTH || iban.length > IBAN_MAX_LENGTH) return false
  // The case-insensitive match lets a few non-ASCII letters through (the Kelvin sign).
  if (!/^[A-Z0-9]+$/.test(iban)) return false
  const rearranged = iban.slice(4) + iban.slice(0, 4)
  const digits = rearranged.replace(/[A-Z]/g, (letter) => String(parseInt(letter, 36)))
  return BigInt(digits) % IBAN_MODULUS === 1n
}

function isLikelyPhone(candidate: string): boolean {
  const trimmed = candidate.trim()
  const digitCount = trimmed.replace(/\D/g, '').length
  if (digitCount < PHONE_MIN_DIGITS || digitCount > PHONE_MAX_DIGITS) return false
  return !DATE_LIKE.test(trimmed) && !THOUSANDS_GROUPED.test(trimmed)
}

/** Blanks out the matches, so a later pattern doesn't read inside them (an IBAN's digit groups
 *  look like a phone number). */
function without(text: string, matches: readonly string[]): string {
  return matches.reduce((rest, match) => rest.replace(match, ' '.repeat(match.length)), text)
}

/**
 * The kinds of personal data a description seems to contain: email addresses, phone numbers,
 * IBANs (checksum-valid only) and likely person names (a courtesy title or a common first name
 * before a capitalised word). Runs in the browser only.
 */
export function findPersonalData(text: string): PersonalDataKind[] {
  const emails = text.match(EMAIL) ?? []
  const ibans = (text.match(IBAN_CANDIDATE) ?? []).filter(isValidIban)
  const rest = without(text, [...emails, ...ibans])
  const hasPhone = (rest.match(PHONE_CANDIDATE) ?? []).some(isLikelyPhone)
  const hasName = TITLE_AND_NAME.test(rest) || FIRST_AND_LAST_NAME.test(rest)
  const found: Record<PersonalDataKind, boolean> = {
    email: emails.length > 0,
    phone: hasPhone,
    iban: ibans.length > 0,
    name: hasName,
  }
  return PERSONAL_DATA_KINDS.filter((kind) => found[kind])
}
