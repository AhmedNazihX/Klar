import { SITE_ACCURACY, type AccuracyFigure } from '@/lib/accuracy'

type Language = 'en' | 'de'

const LOCALES: Record<Language, string> = { en: 'en-GB', de: 'de-DE' }

/**
 * The committed accuracy.json as the pages should show it, worked out here with Intl directly
 * (P27). The tests read whatever the file holds, so a rerun of `aiact evaluate site-metrics` for
 * other runs never breaks them; the backend test checks the file against eval/reports/final.md.
 */
export function publishedAccuracy(language: Language) {
  const { risk_class_accuracy, false_low_risk_rate, citations_exist, head_to_head } = SITE_ACCURACY
  const { scored_cases, own_cases, run_date, report } = SITE_ACCURACY
  if (
    !risk_class_accuracy ||
    !false_low_risk_rate ||
    !citations_exist ||
    !head_to_head ||
    scored_cases === null ||
    own_cases === null ||
    run_date === null ||
    report === null
  ) {
    throw new Error('accuracy.json holds a null; rerun aiact evaluate site-metrics')
  }
  const percent = (figure: AccuracyFigure) =>
    new Intl.NumberFormat(LOCALES[language], {
      style: 'percent',
      maximumFractionDigits: 1,
    }).format(figure.value)
  return {
    /** Each tile's figure line, in order; the last is Klar against the checker. */
    tiles: [
      percent(risk_class_accuracy),
      percent(false_low_risk_rate),
      percent(citations_exist),
      `${percent(head_to_head.klar)}${language === 'de' ? 'vs.' : 'vs'}${percent(head_to_head.checker)}`,
    ],
    cases: head_to_head.cases,
    checkerName: head_to_head.checker_name,
    scoredCases: scored_cases.count,
    ownCases: own_cases.count,
    runDate: new Intl.DateTimeFormat(LOCALES[language], {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone: 'UTC',
    }).format(new Date(`${run_date}T00:00:00Z`)),
    report,
  }
}

/** Intl writes a no-break space before % in German; tests compare it as a plain space. */
export function plainSpaces(text: string | null | undefined): string | undefined {
  return text?.replace(/\s/g, ' ')
}
