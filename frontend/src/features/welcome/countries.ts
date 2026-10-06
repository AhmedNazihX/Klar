// The countries the "Where you are established" field offers, as ISO 3166-1 alpha-2 codes. Names
// come from Intl.DisplayNames in the active language, so no country list is translated by hand.

/** The 27 EU member states. */
export const EU_MEMBER_STATES: ReadonlySet<string> = new Set(
  'AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK'.split(' '),
)

const OTHER_COUNTRIES =
  'AD AE AL AM AR AU AZ BA BD BH BR BY CA CH CL CN CO CR DZ EC EG GB GE HK ID IL IN IQ IR IS JO JP ' +
  'KE KR KW KZ LB LI MA MC MD ME MK MX MY NG NO NZ OM PE PH PK QA RS RU SA SG SM TH TN TR TW UA ' +
  'US UY UZ VE VN ZA'

const ALL_CODES: readonly string[] = [...EU_MEMBER_STATES, ...OTHER_COUNTRIES.split(' ')]

export type CountryOption = { code: string; name: string }

/** Every country the field offers, named and sorted in `language`. */
export function countryOptions(language: string): CountryOption[] {
  const names = new Intl.DisplayNames([language], { type: 'region' })
  const collator = new Intl.Collator(language)
  return ALL_CODES.map((code) => ({ code, name: names.of(code) ?? code })).sort((a, b) =>
    collator.compare(a.name, b.name),
  )
}

/** True for a country outside the EU (the Art. 2(1)(c) and Art. 22 case). */
export function isOutsideEu(code: string | null): boolean {
  return code !== null && !EU_MEMBER_STATES.has(code)
}
