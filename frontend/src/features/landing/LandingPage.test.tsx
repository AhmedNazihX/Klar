import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import { LANGUAGE_STORAGE_KEY } from '@/i18n'
import { stubIntersectionObserver } from '@/test/intersection-observer'
import { stubReducedMotion } from '@/test/reduced-motion'
import { renderRoute } from '@/test/test-utils'

type Language = 'en' | 'de'

const FIRST_LOAD_MS = 8000

async function openLanding(language: Language) {
  const rendered = renderRoute(language === 'de' ? '/de' : '/')
  // The first test loads the page's code-split chunk, which can take a few seconds.
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_LOAD_MS })
  return rendered
}

function section(name: string | RegExp): HTMLElement {
  return screen.getByRole('region', { name })
}

// Every section of the Main and MainDE artboards, with its heading and the lines that prove it.
const PAGE: Record<
  Language,
  { headline: string; sections: { title: string; shows: (string | RegExp)[] }[] }
> = {
  en: {
    headline: 'Where does your AI tool stand under the AI Act?',
    sections: [
      {
        title: 'Where does your AI tool stand under the AI Act?',
        shows: [
          'Updated for the Digital Omnibus, in force since 27 July 2026',
          'Free, no account needed. Guidance, not legal advice.',
          "See how it's measured",
          'Your description',
          'Yes: recruitment, Annex III 4(a)',
          /performs profiling of natural persons/,
          'Stated: scores and ranks',
          'No separate duty found',
          "You're the deployer. Duties apply from 2 December 2027.",
          'Open the to-do list',
        ],
      },
      {
        title: 'The dates moved in July 2026.',
        shows: [
          /Regulation \(EU\) 2026\/1744/,
          '2 Aug 2026',
          '2 Dec 2026',
          '2 Dec 2027',
          '2 Aug 2028',
          'Transparency duties under Article 50 apply.',
          'High-risk duties for AI in products covered by EU product law (Annex I).',
        ],
      },
      {
        title: "It checks in the Act's order, and shows its work.",
        shows: [
          'Scope',
          'Prohibited practices',
          'High-risk',
          'Transparency',
          'Art. 6, Annex III, Annex I',
          /including the Article 25 switch/,
          'Stated',
          'Inferred',
          'Assumed',
          'a default we ask you to confirm',
        ],
      },
      {
        title: "When it isn't sure, it says so.",
        shows: [
          'Needs more information',
          'Legally ambiguous',
          'Does the shift planner use performance or behaviour data to assign work?',
          'Not sure',
          'Narrow procedural task, Art. 6(3)(a)',
          'Not high-risk',
          /assumed high-risk pending legal review/,
        ],
      },
      {
        title: 'From one tool to your whole list.',
        shows: [
          'AI inventory',
          'Applicant screening',
          'Limited risk',
          'Obligations checklist',
          'Art. 26(11)',
          'Draft documents',
          'DRAFT',
          'To fill in: start date',
        ],
      },
      {
        title: 'Accuracy is measured and published, not promised.',
        shows: [
          'Risk-class accuracy',
          'False low-risk rate',
          'Citations that exist',
          'Against an existing checker',
          'The same 25 cases run through EU AI Act Compliance Checker',
          'Read the method and the full results',
        ],
      },
      {
        title: 'Your other AI agents can ask it too.',
        shows: [
          'search_ai_act',
          'get_provision',
          'list_obligations',
          'Exact text of an article',
          'The full engine on one tool',
        ],
      },
      {
        title: "Start with the tool you're least sure about.",
        shows: ['It takes a few sentences. You can add the rest of your list later.'],
      },
    ],
  },
  de: {
    headline: 'Wo steht Ihr KI‑Tool nach der KI‑Verordnung?',
    sections: [
      {
        title: 'Wo steht Ihr KI‑Tool nach der KI‑Verordnung?',
        shows: [
          'Aktualisiert für den Digital-Omnibus, in Kraft seit 27. Juli 2026',
          'Kostenlos, ohne Konto. Orientierungshilfe, keine Rechtsberatung.',
          'So wird gemessen',
          'Ihre Beschreibung',
          'Ja: Einstellung, Anhang III Nr. 4 Buchst. a',
          /wenn es ein Profiling natürlicher Personen vornimmt/,
          'Angegeben: bewertet und reiht',
          'Keine gesonderte Pflicht gefunden',
          'Sie sind Betreiber. Die Pflichten gelten ab 2. Dezember 2027.',
          'Zur Aufgabenliste',
        ],
      },
      {
        title: 'Die Fristen haben sich im Juli 2026 verschoben.',
        shows: [
          /Verordnung \(EU\) 2026\/1744/,
          '2. Aug. 2026',
          '2. Dez. 2026',
          '2. Dez. 2027',
          '2. Aug. 2028',
          'Die Transparenzpflichten nach Artikel 50 gelten.',
          'Hochrisiko-Pflichten für KI in Produkten, die unter EU-Produktrecht fallen (Anhang I).',
        ],
      },
      {
        title: 'Klar prüft in der Reihenfolge der Verordnung und zeigt jeden Schritt.',
        shows: [
          'Anwendungsbereich',
          'Verbotene Praktiken',
          'Hochrisiko',
          'Transparenz',
          'Art. 6, Anhang III, Anhang I',
          /einschließlich des Rollenwechsels nach Artikel 25/,
          'Angegeben',
          'Abgeleitet',
          'Angenommen',
          'eine Annahme, die Sie bestätigen',
        ],
      },
      {
        title: 'Wenn Klar unsicher ist, sagt es das.',
        shows: [
          'Weitere Angaben nötig',
          'Rechtlich unklar',
          'Nutzt die Schichtplanung Leistungs- oder Verhaltensdaten, um Arbeit zuzuteilen?',
          'Unsicher',
          'Eng gefasste Verfahrensaufgabe, Art. 6 Abs. 3 Buchst. a',
          'Kein Hochrisiko',
          /Hochrisiko angenommen, rechtliche Prüfung ausstehend/,
        ],
      },
      {
        title: 'Vom einzelnen Tool zur ganzen Liste.',
        shows: [
          'KI-Inventar',
          'Bewerbervorauswahl',
          'Begrenztes Risiko',
          'Pflichten-Checkliste',
          'Art. 26 Abs. 11',
          'Dokumententwürfe',
          'ENTWURF',
          'Noch auszufüllen: Starttermin',
        ],
      },
      {
        title: 'Genauigkeit wird gemessen und veröffentlicht, nicht versprochen.',
        shows: [
          'Genauigkeit der Risikoklasse',
          'Anteil zu niedrig eingestufter Fälle',
          'Zitate, die existieren',
          'Im Vergleich zu einem bestehenden Prüftool',
          'Dieselben 25 Fälle, geprüft mit EU AI Act Compliance Checker',
          'Methode und vollständige Ergebnisse lesen',
        ],
      },
      {
        title: 'Auch Ihre anderen KI-Agenten können fragen.',
        shows: [
          'search_ai_act',
          'get_provision',
          'list_obligations',
          'Genauer Wortlaut eines Artikels',
          'Die vollständige Prüfung für ein Tool',
        ],
      },
      {
        title: 'Beginnen Sie mit dem Tool, bei dem Sie am unsichersten sind.',
        shows: ['Ein paar Sätze genügen. Den Rest Ihrer Liste ergänzen Sie später.'],
      },
    ],
  },
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe.each(['en', 'de'] as const)('the landing page (%s)', (language) => {
  it('opens in its own language', async () => {
    await i18n.changeLanguage(language === 'de' ? 'en' : 'de')
    await openLanding(language)
    expect(i18n.resolvedLanguage).toBe(language)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(PAGE[language].headline)
  })

  it.each(PAGE[language].sections.map((entry) => [entry.title, entry] as const))(
    'shows the section "%s"',
    async (_, { title, shows }) => {
      await openLanding(language)
      const region = within(section(title))
      for (const text of shows) expect(region.getAllByText(text).length).toBeGreaterThan(0)
    },
  )

  it('shows the figures accuracy.json publishes, none as a placeholder', async () => {
    await openLanding(language)
    const accuracy = section(PAGE[language].sections[5]?.title ?? '')
    expect(accuracy.querySelectorAll('[data-placeholder]')).toHaveLength(0)
    expect(
      within(accuracy)
        .getAllByRole('listitem')
        // Intl puts a no-break space before % in German; compare it as a plain space.
        .map((tile) => tile.firstElementChild?.firstElementChild?.textContent.replace(/\s/g, ' ')),
    ).toEqual(
      language === 'de'
        ? ['65,8 %', '0 %', '100 %', '76 %vs.84 %']
        : ['65.8%', '0%', '100%', '76%vs84%'],
    )
  })

  it('gives the nav its section targets', async () => {
    const { container } = await openLanding(language)
    for (const id of ['how', 'accuracy', 'agents']) {
      expect(container.querySelector(`section#${id}`)).not.toBeNull()
    }
  })

  it('links the actions to the app and the method page', async () => {
    await openLanding(language)
    const action = language === 'de' ? 'Tool einstufen' : 'Classify a tool'
    const hero = within(section(PAGE[language].headline))
    expect(hero.getByRole('link', { name: action })).toHaveAttribute('href', '/app')
    expect(
      screen.getByRole('link', {
        name:
          language === 'de'
            ? 'Methode und vollständige Ergebnisse lesen'
            : 'Read the method and the full results',
      }),
    ).toHaveAttribute('href', '/method')
  })

  it('ends with the footer: 30 days and the four site pages', async () => {
    await openLanding(language)
    const footer = within(screen.getByRole('contentinfo'))
    expect(
      footer.getByText(
        language === 'de'
          ? /nach 30 Tagen ohne Aktivität/
          : /deleted after 30 days without activity/,
      ),
    ).toBeInTheDocument()
    expect(footer.getAllByRole('link')).toHaveLength(4)
  })

  it('has no detectable accessibility violations', async () => {
    const { container } = await openLanding(language)
    // jsdom cannot paint, so colour contrast is checked in the browser (P13).
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})

describe('the quoted provision', () => {
  // Art. 6(3) in the hero's deciding check, in each language's own quotation marks.
  it.each([
    [
      'en',
      '“…an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons.”',
    ],
    [
      'de',
      '„… gilt ein in Anhang III aufgeführtes KI-System immer dann als hochriskant, wenn es ein Profiling natürlicher Personen vornimmt.“',
    ],
  ] as const)('is quoted the %s way', async (language, quote) => {
    await openLanding(language)
    expect(screen.getByText(quote)).toBeInTheDocument()
  })
})

describe('the saved language', () => {
  // The address picks the landing page's language; only the EN/DE switch changes the saved choice.
  it.each([
    ['de', 'en', 'Where does your AI tool stand under the AI Act?'],
    ['en', 'de', 'Wo steht Ihr KI‑Tool nach der KI‑Verordnung?'],
  ] as const)(
    'keeps a saved %s choice when the %s landing page opens',
    async (saved, page, headline) => {
      await i18n.changeLanguage(saved)
      expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe(saved)
      await openLanding(page)
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(headline)
      expect(i18n.resolvedLanguage).toBe(page)
      expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe(saved)
    },
  )

  it('saves the choice made with the EN/DE switch, and the German page keeps it', async () => {
    const user = userEvent.setup()
    const { router } = await openLanding('en')
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en')
    const nav = within(screen.getByRole('navigation', { name: 'Main' }))
    await user.click(nav.getByRole('button', { name: 'Deutsch' }))
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/de')
    })
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('de')
  })
})

describe('the timeline', () => {
  it('marks the dates that apply already and the ones to come, in words', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 10, 12))
    await openLanding('en')
    vi.useRealTimers()
    const dates = within(section('The dates moved in July 2026.'))
    expect(dates.getAllByText('Applies already')).toHaveLength(1)
    expect(dates.getAllByText('Still to come')).toHaveLength(3)
    // Today sits 69 of the 122 days from 2 August to 2 December along the line.
    const fill = dates.getByTestId('timeline-fill')
    expect(fill.style.width).toContain(`calc(${69 / 122} *`)
    expect(dates.getAllByText('Today').length).toBeGreaterThan(0)
  })
})

describe('the agent example', () => {
  it('uses only field names of the generated ClassificationResult', async () => {
    const types = readFileSync(resolve(process.cwd(), 'src/api/types.gen.ts'), 'utf-8')
    const block = /export type ClassificationResult = \{([\s\S]*?)\n\};/.exec(types)?.[1] ?? ''
    const fields = new Set(Array.from(block.matchAll(/^ {4}(\w+)\??:/gm), (match) => match[1]))
    expect(fields.size).toBeGreaterThan(10)

    await openLanding('en')
    const code = screen.getByRole('region', { name: 'Example result of classify_system' })
    // Top-level keys only: one indent step in, before the colon.
    const keys = Array.from(
      code.querySelectorAll(':scope > .pl-5'),
      (line) => /^"(\w+)":/.exec(line.textContent)?.[1],
    )
    expect(keys).toEqual([
      'risk_class',
      'status',
      'role',
      'annex_point',
      'steps',
      'law_version',
      'law_text',
      'disclaimer',
    ])
    for (const key of keys) expect(fields.has(key ?? '')).toBe(true)
    expect(code).toHaveTextContent('"law_version": "amended"')
    expect(code).toHaveTextContent('"celex": "02024R1689-20260727"')
  })

  it('keeps the guidance notice in the example, in German too', async () => {
    await openLanding('de')
    const code = screen.getByRole('region', { name: 'Beispielergebnis von classify_system' })
    expect(code).toHaveTextContent(
      '"disclaimer": "Dies ist eine Orientierungshilfe, keine Rechtsberatung. …"',
    )
    expect(code).toHaveTextContent('… 5 Schritte, jeweils mit Zitaten und Herkunftsangabe …')
  })
})

describe('motion', () => {
  it('starts the hero sequence and hides what starts off screen', async () => {
    stubReducedMotion(false)
    const observer = stubIntersectionObserver()
    const { container } = await openLanding('en')
    expect(container.querySelector('#top')).toHaveAttribute('data-intro', 'true')
    const reveals = Array.from(container.querySelectorAll<HTMLElement>('[data-reveal]'))
    expect(reveals.length).toBeGreaterThan(20)
    // jsdom places everything at the top: tell each observer its element is below the window.
    for (const element of observer.observed()) {
      vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(
        DOMRect.fromRect({ x: 0, y: 2000, width: 400, height: 200 }),
      )
      act(() => {
        observer.show(element, false)
      })
    }
    for (const element of reveals) expect(element).toHaveAttribute('data-reveal-at', 'below')
  })

  it('never hides what is on screen when the page loads', async () => {
    stubReducedMotion(false)
    const observer = stubIntersectionObserver()
    const { container } = await openLanding('en')
    for (const element of observer.observed()) {
      act(() => {
        observer.show(element, true)
      })
    }
    expect(container.querySelectorAll('[data-reveal-at]')).toHaveLength(0)
    expect(container.querySelectorAll('[data-typing]')).toHaveLength(0)
  })

  it('shows every element and runs no animation with reduced motion', async () => {
    stubReducedMotion(true)
    const observer = stubIntersectionObserver()
    const { container } = await openLanding('en')
    expect(observer.observed()).toEqual([])
    expect(container.querySelector('[data-intro]')).toBeNull()
    expect(container.querySelector('[data-reveal-at]')).toBeNull()
    expect(container.querySelector('[data-reveal-moving]')).toBeNull()
    expect(container.querySelector('[data-typing]')).toBeNull()
    expect(container.querySelector('[data-light="cursor"]')).toBeNull()
    // The example is complete: its last line is there in full.
    expect(
      screen.getByRole('region', { name: 'Example result of classify_system' }),
    ).toHaveTextContent('"disclaimer": "This is guidance, not legal advice. …"')
  })
})

describe('the site nav on the landing page', () => {
  it('flows the pill from EN to DE on arriving at the German page', async () => {
    stubReducedMotion(false)
    await openLanding('de')
    const nav = within(screen.getByRole('navigation', { name: 'Hauptnavigation' }))
    expect(nav.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => {
      expect(nav.getByRole('button', { name: 'Deutsch' })).toHaveAttribute('aria-pressed', 'true')
    })
  })

  it('puts the pill under DE at once with reduced motion', async () => {
    stubReducedMotion(true)
    await openLanding('de')
    const nav = within(screen.getByRole('navigation', { name: 'Hauptnavigation' }))
    expect(nav.getByRole('button', { name: 'Deutsch' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('turns denser once the page scrolls', async () => {
    await openLanding('en')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(nav).not.toHaveAttribute('data-dense')
    Object.defineProperty(window, 'scrollY', { value: 400, configurable: true })
    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })
    expect(nav).toHaveAttribute('data-dense', 'true')
    expect(nav).toHaveClass('fixed')
    Object.defineProperty(window, 'scrollY', { value: 0, configurable: true })
  })

  it('opens the four links from the Sections menu on a narrow screen', async () => {
    const user = userEvent.setup()
    await openLanding('en')
    const nav = within(screen.getByRole('navigation', { name: 'Main' }))
    const menu = nav.getByRole('button', { name: 'Sections' })
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    await user.click(menu)
    expect(menu).toHaveAttribute('aria-expanded', 'true')
    const panel = within(
      document.getElementById(menu.getAttribute('aria-controls') ?? '') ?? document.body,
    )
    expect(panel.getByRole('link', { name: 'How it works' })).toHaveAttribute('href', '/#how')
    expect(panel.getByRole('link', { name: 'For AI agents' })).toHaveAttribute('href', '/#agents')
    expect(panel.getByRole('link', { name: 'Your data' })).toHaveAttribute('href', '/privacy')
    expect(panel.getByRole('link', { name: 'Classify a tool' })).toHaveAttribute('href', '/app')
    await user.keyboard('{Escape}')
    expect(nav.getByRole('button', { name: 'Sections' })).toHaveAttribute('aria-expanded', 'false')
  })
})
