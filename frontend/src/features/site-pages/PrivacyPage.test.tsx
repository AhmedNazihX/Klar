import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import { markedPlaceholders, unmarkedPlaceholders } from '@/test/placeholders'
import { renderRoute } from '@/test/test-utils'

type Language = 'en' | 'de'

const FIRST_LOAD_MS = 8000

async function openPrivacy(language: Language) {
  await i18n.changeLanguage(language)
  const rendered = renderRoute('/privacy')
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_LOAD_MS })
  return rendered
}

// The decided values (decision 013, 026 items 6, 7, 9 and C3; decision 033 › Privacy wording, as
// widened by the user on 2026-10-10), written out here so a changed string fails the test.
const PAGE: Record<
  Language,
  {
    title: string
    sections: string[]
    retention: string
    stored: string
    questions: string
    processors: { label: string; shows: string[] }[]
    placeholders: string[]
  }
> = {
  en: {
    title: 'Privacy notice',
    sections: [
      'Who is responsible',
      'What Klar processes, and why',
      'What Klar keeps, and for how long',
      'Who else processes it',
      'Your rights',
    ],
    retention:
      'How Klar handles what you type. Short version: your data stays in an anonymous session, is never used to train models, and is deleted after 30 days without activity.',
    stored:
      'Your inventory of tools and their descriptions, their classification results, your answers for draft documents, your company profile and your checklist progress. Only you can see them.',
    questions:
      'Kept only in your browser for this session. Nothing you ask is saved on Klar’s side.',
    processors: [
      {
        label: 'Language models',
        shows: [
          'OpenRouter passes each request on; its own processing isn’t limited to the EU. The models run in EU regions on Microsoft Azure and Google Vertex AI.',
          "If Microsoft Azure's content filter blocks a check or a question to Klar, that request (for a check: the description and the facts and answers taken from it; for a question: the question and the result it's about, if any) is sent once more to Gemini 3.1 Flash-Lite on Google Vertex AI in the EU (zero data retention, no training), for each request the filter blocked. This happens only when the filter blocks it.",
          'Every request to a model is sent with zero data retention and no training.',
        ],
      },
      {
        label: 'Search of the legal texts',
        shows: [
          'Nebius, reached through OpenRouter, turns your description into a search of the Act (embeddings). Nebius was chosen as an EU host, but OpenRouter gives this endpoint no region tag, so its region is [TO CONFIRM WITH NEBIUS].',
        ],
      },
      {
        label: 'Session storage',
        shows: [
          'Supabase keeps your saved data and your anonymous session, visible only to you. Region: [REGION].',
        ],
      },
    ],
    placeholders: [
      '[NAME]',
      '[ADDRESS]',
      '[EMAIL]',
      '[NAME OR “NOT REQUIRED”]',
      '[TO CONFIRM, E.G. ART. 6(1)(B) GDPR]',
      '[LOG RETENTION]',
      '[TO CONFIRM, E.G. ART. 6(1)(F) GDPR]',
      '[TO CONFIRM WITH NEBIUS]',
      '[REGION]',
      '[TO CONFIRM, WITH SAFEGUARDS]',
      '[CONFIRM]',
    ],
  },
  de: {
    title: 'Datenschutzerklärung',
    sections: [
      'Wer verantwortlich ist',
      'Was Klar verarbeitet, und wozu',
      'Was Klar speichert, und wie lange',
      'Wer sie außerdem verarbeitet',
      'Ihre Rechte',
    ],
    retention:
      'Wie Klar mit Ihren Eingaben umgeht. Kurz gesagt: Ihre Daten bleiben in einer anonymen Sitzung, werden nie zum Trainieren von Modellen verwendet und nach 30 Tagen ohne Aktivität gelöscht.',
    stored:
      'Ihre Liste der Tools mit ihren Beschreibungen, deren Ergebnisse der Einstufung, Ihre Antworten für Dokumententwürfe, Ihr Unternehmensprofil und Ihr Fortschritt in den Checklisten. Nur Sie können sie sehen.',
    questions:
      'Nur in Ihrem Browser für diese Sitzung gespeichert. Was Sie fragen, speichert Klar nicht.',
    processors: [
      {
        label: 'Sprachmodelle',
        shows: [
          'OpenRouter leitet jede Anfrage weiter; seine eigene Verarbeitung ist nicht auf die EU beschränkt. Die Modelle laufen in EU-Regionen bei Microsoft Azure und Google Vertex AI.',
          'Blockiert der Inhaltsfilter von Microsoft Azure eine Prüfung oder eine Frage an Klar, wird diese Anfrage (bei einer Prüfung: die Beschreibung sowie die daraus gewonnenen Fakten und Antworten; bei einer Frage: die Frage und, falls vorhanden, das Ergebnis, auf das sie sich bezieht) noch einmal an Gemini 3.1 Flash-Lite bei Google Vertex AI in der EU gesendet (keine Datenspeicherung beim Anbieter, kein Training), für jede blockierte Anfrage. Das geschieht nur, wenn der Filter sie blockiert.',
          'Jede Anfrage an ein Modell wird ohne Datenspeicherung beim Anbieter und ohne Training gestellt.',
        ],
      },
      {
        label: 'Suche in den Rechtstexten',
        shows: [
          'Nebius, über OpenRouter angesprochen, macht aus Ihrer Beschreibung eine Suche in der Verordnung (Embeddings). Nebius wurde als Anbieter in der EU gewählt, aber OpenRouter weist für diesen Endpunkt keine Region aus; die Region ist daher [MIT NEBIUS ZU BESTÄTIGEN].',
        ],
      },
      {
        label: 'Speicherung der Sitzung',
        shows: [
          'Supabase speichert Ihre Daten und Ihre anonyme Sitzung, nur für Sie sichtbar. Region: [REGION].',
        ],
      },
    ],
    placeholders: [
      '[NAME]',
      '[ANSCHRIFT]',
      '[E-MAIL]',
      '[NAME ODER „NICHT ERFORDERLICH“]',
      '[ZU BESTÄTIGEN, Z. B. ART. 6 ABS. 1 BUCHST. B DSGVO]',
      '[DAUER DER PROTOKOLLE]',
      '[ZU BESTÄTIGEN, Z. B. ART. 6 ABS. 1 BUCHST. F DSGVO]',
      '[MIT NEBIUS ZU BESTÄTIGEN]',
      '[REGION]',
      '[ZU BESTÄTIGEN, MIT GARANTIEN]',
      '[BESTÄTIGEN]',
    ],
  },
}

/** The text beside a row's label in a description list. */
function rowText(region: HTMLElement, label: string): HTMLElement {
  const term = within(region).getByText(label, { selector: 'dt' })
  const definition = term.nextElementSibling
  if (!(definition instanceof HTMLElement)) throw new Error(`No text beside "${label}"`)
  return definition
}

// Every line of the page's copy as the user reviews it, in both languages (tags stripped).
const COPY: Record<Language, string[]> = {
  en: [
    'How Klar handles what you type. Short version: your data stays in an anonymous session, is never used to train models, and is deleted after 30 days without activity.',
    'This is a template. Every bracketed field must be completed, and the notice reviewed by a data protection adviser, before launch.',
    'Who is responsible',
    'Controller',
    '[NAME], [ADDRESS]',
    'Contact for privacy',
    '[EMAIL]',
    'Data protection officer',
    '[NAME OR “NOT REQUIRED”]',
    'What Klar processes, and why',
    'Tool descriptions and answers',
    'To classify your tools and draft your documents, the service you ask for. Legal basis: [TO CONFIRM, E.G. ART. 6(1)(B) GDPR].',
    'Questions about the Act',
    'To answer them, with citations. Same basis.',
    'Technical logs',
    'To keep the service secure and working, kept for [LOG RETENTION]. Legal basis: [TO CONFIRM, E.G. ART. 6(1)(F) GDPR].',
    'What Klar never does',
    'Train models on your data, create profiles, or set tracking cookies.',
    'What Klar keeps, and for how long',
    'Saved in your session',
    'Your inventory of tools and their descriptions, their classification results, your answers for draft documents, your company profile and your checklist progress. Only you can see them.',
    'Questions to Klar',
    'Kept only in your browser for this session. Nothing you ask is saved on Klar’s side.',
    'How long',
    'Everything is deleted after 30 days without activity. In the app, Your data deletes it all at once, whenever you like.',
    'Who else processes it',
    'Language models',
    'Search of the legal texts',
    'Nebius, reached through OpenRouter, turns your description into a search of the Act (embeddings). Nebius was chosen as an EU host, but OpenRouter gives this endpoint no region tag, so its region is [TO CONFIRM WITH NEBIUS].',
    'Session storage',
    'Supabase keeps your saved data and your anonymous session, visible only to you. Region: [REGION].',
    'Transfers outside the EU',
    '[TO CONFIRM, WITH SAFEGUARDS]',
    'Your rights',
    'You can ask for access to your data, correction, deletion, restriction, a portable copy, or object to processing (Articles 15 to 21 GDPR). In the app, Your data lets you download or delete everything at once. You can also complain to a supervisory authority; for a company based in North Rhine-Westphalia that is the LDI NRW, the state data protection commissioner [CONFIRM].',
  ],
  de: [
    'Wie Klar mit Ihren Eingaben umgeht. Kurz gesagt: Ihre Daten bleiben in einer anonymen Sitzung, werden nie zum Trainieren von Modellen verwendet und nach 30 Tagen ohne Aktivität gelöscht.',
    'Dies ist eine Vorlage. Vor dem Start muss jedes Feld in eckigen Klammern ausgefüllt und die Erklärung von einer Datenschutzberatung geprüft werden.',
    'Wer verantwortlich ist',
    'Verantwortlicher',
    '[NAME], [ANSCHRIFT]',
    'Kontakt für den Datenschutz',
    '[E-MAIL]',
    'Datenschutzbeauftragte',
    '[NAME ODER „NICHT ERFORDERLICH“]',
    'Was Klar verarbeitet, und wozu',
    'Tool-Beschreibungen und Antworten',
    'Um Ihre Tools einzustufen und Ihre Dokumente zu entwerfen, also für den Dienst, den Sie anfordern. Rechtsgrundlage: [ZU BESTÄTIGEN, Z. B. ART. 6 ABS. 1 BUCHST. B DSGVO].',
    'Fragen zur Verordnung',
    'Um sie mit Zitaten zu beantworten. Dieselbe Rechtsgrundlage.',
    'Technische Protokolle',
    'Um den Dienst sicher und funktionsfähig zu halten, gespeichert für [DAUER DER PROTOKOLLE]. Rechtsgrundlage: [ZU BESTÄTIGEN, Z. B. ART. 6 ABS. 1 BUCHST. F DSGVO].',
    'Was Klar nie tut',
    'Modelle mit Ihren Daten trainieren, Profile erstellen oder Tracking-Cookies setzen.',
    'Was Klar speichert, und wie lange',
    'In Ihrer Sitzung gespeichert',
    'Ihre Liste der Tools mit ihren Beschreibungen, deren Ergebnisse der Einstufung, Ihre Antworten für Dokumententwürfe, Ihr Unternehmensprofil und Ihr Fortschritt in den Checklisten. Nur Sie können sie sehen.',
    'Fragen an Klar',
    'Nur in Ihrem Browser für diese Sitzung gespeichert. Was Sie fragen, speichert Klar nicht.',
    'Wie lange',
    'Alles wird nach 30 Tagen ohne Aktivität gelöscht. In der App löscht „Ihre Daten“ alles auf einmal, wann immer Sie möchten.',
    'Wer sie außerdem verarbeitet',
    'Sprachmodelle',
    'Suche in den Rechtstexten',
    'Nebius, über OpenRouter angesprochen, macht aus Ihrer Beschreibung eine Suche in der Verordnung (Embeddings). Nebius wurde als Anbieter in der EU gewählt, aber OpenRouter weist für diesen Endpunkt keine Region aus; die Region ist daher [MIT NEBIUS ZU BESTÄTIGEN].',
    'Speicherung der Sitzung',
    'Supabase speichert Ihre Daten und Ihre anonyme Sitzung, nur für Sie sichtbar. Region: [REGION].',
    'Übermittlungen außerhalb der EU',
    '[ZU BESTÄTIGEN, MIT GARANTIEN]',
    'Ihre Rechte',
    'Sie können Auskunft über Ihre Daten, Berichtigung, Löschung, Einschränkung und eine übertragbare Kopie verlangen oder der Verarbeitung widersprechen (Artikel 15 bis 21 DSGVO). In der App können Sie unter „Ihre Daten“ alles auf einmal herunterladen oder löschen. Außerdem können Sie sich bei einer Aufsichtsbehörde beschweren; für ein Unternehmen mit Sitz in Nordrhein-Westfalen ist das die LDI NRW, die Landesbeauftragte für Datenschutz und Informationsfreiheit [BESTÄTIGEN].',
  ],
}

describe.each(['en', 'de'] as const)('the privacy notice (%s)', (language) => {
  const page = PAGE[language]

  it('shows the artboard’s sections, the template note and the 30 days', async () => {
    await openPrivacy(language)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(page.title)
    expect(
      within(screen.getByRole('main'))
        .getAllByRole('heading', { level: 2 })
        .map((heading) => heading.textContent),
    ).toEqual(page.sections)
    expect(screen.getByRole('note')).toBeInTheDocument()
    expect(screen.getByText(page.retention)).toBeInTheDocument()
  })

  it('says what Klar keeps, and that questions stay in the browser', async () => {
    await openPrivacy(language)
    const kept = screen.getByRole('region', { name: page.sections[2] })
    expect(within(kept).getByText(page.stored)).toBeInTheDocument()
    expect(within(kept).getByText(page.questions)).toBeInTheDocument()
    expect(kept).toHaveTextContent(language === 'en' ? '30 days' : 'nach 30 Tagen ohne Aktivität')
  })

  it('names every processor, with the refusal route word for word', async () => {
    await openPrivacy(language)
    const processors = screen.getByRole('region', { name: page.sections[3] })
    for (const { label, shows } of page.processors) {
      const text = rowText(processors, label)
      for (const line of shows) expect(text).toHaveTextContent(line, { normalizeWhitespace: true })
    }
  })

  it('marks every unknown as a placeholder', async () => {
    await openPrivacy(language)
    const main = screen.getByRole('main')
    expect(unmarkedPlaceholders(main)).toEqual([])
    expect(markedPlaceholders(main)).toEqual(page.placeholders)
  })

  it('has no detectable accessibility violations', async () => {
    const { container } = await openPrivacy(language)
    // jsdom cannot paint, so colour contrast is checked in the browser.
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})

describe.each(['en', 'de'] as const)('the privacy page copy (%s)', (language) => {
  it('shows every line of the reviewed copy', async () => {
    await openPrivacy(language)
    const main = screen.getByRole('main')
    for (const line of COPY[language]) expect(main).toHaveTextContent(line)
  })
})
