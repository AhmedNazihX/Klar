import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import accuracyFile from '@/content/accuracy.json'
import { SITE_ACCURACY, type SiteAccuracy } from '@/lib/accuracy'
import { markedPlaceholders, unmarkedPlaceholders } from '@/test/placeholders'
import { renderRoute, renderWithProviders } from '@/test/test-utils'

import { MethodPage } from './MethodPage'

type Language = 'en' | 'de'

const FIRST_LOAD_MS = 8000

async function openMethod(language: Language) {
  await i18n.changeLanguage(language)
  const rendered = renderRoute('/method')
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_LOAD_MS })
  return rendered
}

const PAGE: Record<
  Language,
  {
    title: string
    sections: string[]
    penalties: string
    lawVersion: string
    placeholders: string[]
  }
> = {
  en: {
    title: 'How Klar is measured',
    sections: ['The test set', 'What we count', 'How a case is scored', 'Limits', 'Results'],
    penalties:
      'Klar covers the Act’s own maximum fines (Art. 99). National penalty rules, which each Member State lays down, are out of scope.',
    lawVersion: 'Consolidated AI Act of 27 July 2026, CELEX 02024R1689-20260727',
    placeholders: [
      '[N]',
      '[WHO LABELS THE CASES]',
      '[—%]',
      '[—%]',
      '[—%]',
      '[—%]',
      '[—%]',
      '[N]',
      '[CHECKER NAME]',
      '[N]',
      '[WHO LABELS THE CASES]',
      '[DATE]',
      '[LINK TO THE EVALUATION REPORT]',
    ],
  },
  de: {
    title: 'So wird Klar gemessen',
    sections: [
      'Der Testdatensatz',
      'Was wir zählen',
      'So wird ein Fall bewertet',
      'Grenzen',
      'Ergebnisse',
    ],
    penalties:
      'Klar deckt die Höchstbeträge der Geldbußen ab, die die Verordnung selbst festlegt (Art. 99). Nationale Sanktionsvorschriften, die jeder Mitgliedstaat erlässt, sind nicht abgedeckt.',
    lawVersion: 'Konsolidierte KI-Verordnung vom 27. Juli 2026, CELEX 02024R1689-20260727',
    placeholders: [
      '[N]',
      '[WER DIE FÄLLE KENNZEICHNET]',
      '[—%]',
      '[—%]',
      '[—%]',
      '[—%]',
      '[—%]',
      '[N]',
      '[NAME DES PRÜFTOOLS]',
      '[N]',
      '[WER DIE FÄLLE KENNZEICHNET]',
      '[DATUM]',
      '[LINK ZUM EVALUATIONSBERICHT]',
    ],
  },
}

const MEASURED: SiteAccuracy = {
  risk_class_accuracy: { value: 0.875, run_id: 'run-a' },
  false_low_risk_rate: { value: 0.04, run_id: 'run-a' },
  citations_exist: { value: 1, run_id: 'run-a' },
  head_to_head: {
    klar: { value: 0.8, run_id: 'run-b' },
    checker: { value: 0.55, run_id: 'run-b' },
    checker_name: 'the Commission checker',
    cases: 24,
  },
}

// Every line of the page's copy as the user reviews it, in both languages (tags stripped).
const COPY: Record<Language, string[]> = {
  en: [
    'Accuracy is something we test and publish, not something we promise. This page explains the test set, what we count, and where the method has limits.',
    'The test set',
    'The main test set is built from the Commission’s own worked examples of high-risk and not-high-risk systems, plus [N] cases written for Klar. Half of the Commission examples are removed from everything Klar can search, so it can’t simply look the answers up. Each case is labelled with its correct class and role by [WHO LABELS THE CASES].',
    'What we count',
    'Share of cases where Klar’s class matches the label: prohibited, high-risk, limited, minimal or out of scope.',
    'Share of prohibited or high-risk cases that Klar labelled lower. This is the costliest error, so we report it on its own.',
    'Share of cited provisions that exist in the legal text and say what Klar claims. Checked automatically against the consolidated Act.',
    'The same [N] cases run through [CHECKER NAME], scored the same way.',
    'How a case is scored',
    'Run',
    'Every case goes through the full engine, in the Act’s order, with the same settings users get.',
    'Compare',
    'The class, role and deciding provision are compared with the label.',
    'Check citations',
    'Every cited provision is looked up in the legal text, by number.',
    'Count uncertainty honestly',
    'A “needs more information” or “legally ambiguous” result counts as correct only if the label agrees the case is open.',
    'Limits',
    'Size',
    'The test set has [N] cases. Small differences between runs are not meaningful.',
    'Labels',
    'Labels reflect [WHO LABELS THE CASES]’s reading of the Act and may be disputed.',
    'Guidance',
    'Some Commission guidance is still in draft; results may shift when it’s final.',
    'Descriptions',
    'Real users describe tools less completely than test cases do. Klar is only as accurate as the description it gets.',
    'Penalties',
    'Klar covers the Act’s own maximum fines (Art. 99). National penalty rules, which each Member State lays down, are out of scope.',
    'Results',
    'Last run',
    '[DATE]',
    'Law version',
    'Consolidated AI Act of 27 July 2026, CELEX 02024R1689-20260727',
    'Full results',
    '[LINK TO THE EVALUATION REPORT]',
  ],
  de: [
    'Genauigkeit testen und veröffentlichen wir, statt sie zu versprechen. Diese Seite erklärt den Testdatensatz, was wir zählen und wo die Methode an Grenzen stößt.',
    'Der Testdatensatz',
    'Der wichtigste Testdatensatz stammt aus den Beispielen der Kommission für Hochrisiko- und andere Systeme, ergänzt um [N] eigens für Klar geschriebene Fälle. Die Hälfte der Kommissionsbeispiele ist aus allem entfernt, was Klar durchsuchen kann, damit es die Antworten nicht einfach nachschlägt. Jeder Fall ist mit seiner richtigen Klasse und Rolle gekennzeichnet, von [WER DIE FÄLLE KENNZEICHNET].',
    'Was wir zählen',
    'Anteil der Fälle, in denen die Klasse von Klar mit dem Label übereinstimmt: verboten, Hochrisiko, begrenztes Risiko, minimales Risiko oder außerhalb des Anwendungsbereichs.',
    'Anteil der verbotenen oder Hochrisiko-Fälle, die Klar niedriger eingestuft hat. Das ist der teuerste Fehler, deshalb weisen wir ihn gesondert aus.',
    'Anteil der zitierten Vorschriften, die im Gesetzestext existieren und sagen, was Klar behauptet. Automatisch an der konsolidierten Verordnung geprüft.',
    'Dieselben [N] Fälle, geprüft mit [NAME DES PRÜFTOOLS] und genauso bewertet.',
    'So wird ein Fall bewertet',
    'Durchlauf',
    'Jeder Fall durchläuft die vollständige Prüfung in der Reihenfolge der Verordnung, mit denselben Einstellungen wie für alle Nutzer.',
    'Vergleich',
    'Klasse, Rolle und entscheidende Vorschrift werden mit dem Label verglichen.',
    'Zitate prüfen',
    'Jede zitierte Vorschrift wird anhand ihrer Nummer im Gesetzestext nachgeschlagen.',
    'Unsicherheit ehrlich zählen',
    'Ein Ergebnis „Weitere Angaben nötig“ oder „Rechtlich unklar“ zählt nur dann als richtig, wenn auch das Label den Fall als offen einstuft.',
    'Grenzen',
    'Umfang',
    'Der Testdatensatz umfasst [N] Fälle. Kleine Unterschiede zwischen zwei Durchläufen sind nicht aussagekräftig.',
    'Labels',
    'Die Labels geben die Lesart der Verordnung von [WER DIE FÄLLE KENNZEICHNET] wieder und können umstritten sein.',
    'Leitlinien',
    'Einige Leitlinien der Kommission sind noch Entwürfe; die Ergebnisse können sich ändern, wenn sie endgültig sind.',
    'Beschreibungen',
    'Echte Nutzer beschreiben Tools weniger vollständig als Testfälle. Klar ist nur so genau wie die Beschreibung, die es erhält.',
    'Sanktionen',
    'Klar deckt die Höchstbeträge der Geldbußen ab, die die Verordnung selbst festlegt (Art. 99). Nationale Sanktionsvorschriften, die jeder Mitgliedstaat erlässt, sind nicht abgedeckt.',
    'Ergebnisse',
    'Letzter Durchlauf',
    '[DATUM]',
    'Fassung des Gesetzes',
    'Konsolidierte KI-Verordnung vom 27. Juli 2026, CELEX 02024R1689-20260727',
    'Vollständige Ergebnisse',
    '[LINK ZUM EVALUATIONSBERICHT]',
  ],
}

describe.each(['en', 'de'] as const)('the method page (%s)', (language) => {
  const page = PAGE[language]

  it('shows the artboard’s sections in order', async () => {
    await openMethod(language)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(page.title)
    const main = screen.getByRole('main')
    expect(
      within(main)
        .getAllByRole('heading', { level: 2 })
        .map((heading) => heading.textContent),
    ).toEqual(page.sections)
  })

  it('names national penalty rules as out of scope and the law version it measured', async () => {
    await openMethod(language)
    const limits = screen.getByRole('region', { name: page.sections[3] })
    expect(within(limits).getByText(page.penalties)).toBeInTheDocument()
    const results = screen.getByRole('region', { name: page.sections[4] })
    expect(within(results).getByText(page.lawVersion)).toBeInTheDocument()
  })

  it('marks every unknown as a placeholder', async () => {
    await openMethod(language)
    const main = screen.getByRole('main')
    expect(unmarkedPlaceholders(main)).toEqual([])
    expect(markedPlaceholders(main)).toEqual(page.placeholders)
  })

  it('has no detectable accessibility violations', async () => {
    const { container } = await openMethod(language)
    // jsdom cannot paint, so colour contrast is checked in the browser.
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})

describe('the method figures', () => {
  it('come from the same accuracy.json as the landing page', () => {
    expect(SITE_ACCURACY).toEqual(accuracyFile)
  })

  it('show the measured values once accuracy.json has them', async () => {
    renderWithProviders(<MethodPage accuracy={MEASURED} />)
    const counted = await screen.findByRole('region', { name: 'What we count' })
    // Each tile's figure line, in order; the last is Klar against the checker.
    expect(
      within(counted)
        .getAllByRole('listitem')
        .map((tile) => tile.firstElementChild?.textContent),
    ).toEqual(['87.5%', '4%', '100%', '80%vs55%'])
    expect(
      within(counted).getByText(
        'The same 24 cases run through the Commission checker, scored the same way.',
      ),
    ).toBeInTheDocument()
    expect(markedPlaceholders(counted)).toEqual([])
  })

  it('show them in German number format', async () => {
    await i18n.changeLanguage('de')
    renderWithProviders(<MethodPage accuracy={MEASURED} />)
    const counted = await screen.findByRole('region', { name: 'Was wir zählen' })
    expect(within(counted).getAllByRole('listitem')[0]?.firstElementChild).toHaveTextContent(
      '87,5 %',
    )
    expect(
      within(counted).getByText(
        'Dieselben 24 Fälle, geprüft mit the Commission checker und genauso bewertet.',
      ),
    ).toBeInTheDocument()
  })
})

describe.each(['en', 'de'] as const)('the method page copy (%s)', (language) => {
  it('shows every line of the reviewed copy', async () => {
    await openMethod(language)
    const main = screen.getByRole('main')
    for (const line of COPY[language]) expect(main).toHaveTextContent(line)
  })
})
