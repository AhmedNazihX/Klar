import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import { markedPlaceholders, unmarkedPlaceholders } from '@/test/placeholders'
import { renderRoute } from '@/test/test-utils'

type Language = 'en' | 'de'

const FIRST_LOAD_MS = 8000

async function openContact(language: Language) {
  await i18n.changeLanguage(language)
  const rendered = renderRoute('/contact')
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_LOAD_MS })
  return rendered
}

const PAGE: Record<
  Language,
  {
    title: string
    sections: string[]
    topicGroup: string
    send: string
    topics: { button: string; href: string }[]
    askLink: string
    yourDataLink: string
    placeholders: string[]
  }
> = {
  en: {
    title: 'Contact',
    sections: ['Write to us', 'Legal questions', 'Privacy requests'],
    topicGroup: 'What is it about?',
    send: 'Write an email',
    topics: [
      {
        button: 'A question about Klar',
        href: 'mailto:?subject=Klar%3A%20a%20question%20about%20Klar',
      },
      { button: 'Feedback', href: 'mailto:?subject=Klar%3A%20feedback' },
      { button: 'Privacy request', href: 'mailto:?subject=Klar%3A%20privacy%20request' },
    ],
    askLink: 'Ask about the Act',
    yourDataLink: 'Your data',
    placeholders: ['[RESPONSE TIME]', '[CONTACT EMAIL]', '[PRIVACY EMAIL]'],
  },
  de: {
    title: 'Kontakt',
    sections: ['Schreiben Sie uns', 'Rechtsfragen', 'Datenschutzanfragen'],
    topicGroup: 'Worum geht es?',
    send: 'E-Mail schreiben',
    topics: [
      { button: 'Eine Frage zu Klar', href: 'mailto:?subject=Klar%3A%20Frage%20zu%20Klar' },
      { button: 'Feedback', href: 'mailto:?subject=Klar%3A%20Feedback' },
      { button: 'Datenschutzanfrage', href: 'mailto:?subject=Klar%3A%20Datenschutzanfrage' },
    ],
    askLink: 'Fragen zur KI-Verordnung',
    yourDataLink: 'Ihre Daten',
    placeholders: ['[ANTWORTZEIT]', '[KONTAKT-E-MAIL]', '[DATENSCHUTZ-E-MAIL]'],
  },
}

// Every line of the page's copy as the user reviews it, in both languages (tags stripped).
const COPY: Record<Language, string[]> = {
  en: [
    'Questions about Klar, feedback, or a privacy request. We read everything and reply within [RESPONSE TIME].',
    'Write to us',
    'What is it about?',
    'A question about Klar',
    'Feedback',
    'Privacy request',
    'Email',
    '[CONTACT EMAIL]',
    'Write an email',
    'This opens your email program with the subject filled in. Klar has no contact form and keeps nothing you send here.',
    'Leave out personal details of applicants or staff.',
    'Legal questions',
    'We can’t give legal advice by email. For questions about the AI Act itself, Ask about the Act answers with citations; for your own case, talk to a lawyer.',
    'Ask about the Act',
    'Privacy requests',
    'To download or delete your data right away, use Your data in the app. Otherwise write to [PRIVACY EMAIL].',
  ],
  de: [
    'Fragen zu Klar, Feedback oder eine Datenschutzanfrage. Wir lesen alles und antworten innerhalb von [ANTWORTZEIT].',
    'Schreiben Sie uns',
    'Worum geht es?',
    'Eine Frage zu Klar',
    'Feedback',
    'Datenschutzanfrage',
    'E-Mail',
    '[KONTAKT-E-MAIL]',
    'E-Mail schreiben',
    'Damit öffnet sich Ihr E-Mail-Programm mit ausgefülltem Betreff. Klar hat kein Kontaktformular und speichert nichts, was Sie hier senden.',
    'Lassen Sie personenbezogene Angaben zu Bewerbenden oder Beschäftigten weg.',
    'Rechtsfragen',
    'Per E-Mail können wir keine Rechtsberatung geben. Fragen zur KI-Verordnung selbst beantwortet „Fragen zur KI-Verordnung“ mit Zitaten; für Ihren eigenen Fall sprechen Sie mit einer Anwältin oder einem Anwalt.',
    'Fragen zur KI-Verordnung',
    'Datenschutzanfragen',
    'Um Ihre Daten sofort herunterzuladen oder zu löschen, nutzen Sie Ihre Daten in der App. Andernfalls schreiben Sie an [DATENSCHUTZ-E-MAIL].',
  ],
}

describe.each(['en', 'de'] as const)('the contact page (%s)', (language) => {
  const page = PAGE[language]

  it('shows the sections, with no form to send', async () => {
    const { container } = await openContact(language)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(page.title)
    expect(
      within(screen.getByRole('main'))
        .getAllByRole('heading', { level: 2 })
        .map((heading) => heading.textContent),
    ).toEqual(page.sections)
    expect(container.querySelector('form, input, textarea')).toBeNull()
    const legal = screen.getByRole('region', { name: page.sections[1] })
    expect(within(legal).getByRole('link', { name: page.askLink })).toHaveAttribute(
      'href',
      '/app/ask',
    )
    const privacy = screen.getByRole('region', { name: page.sections[2] })
    expect(within(privacy).getByRole('link', { name: page.yourDataLink })).toHaveAttribute(
      'href',
      '/app/your-data',
    )
  })

  it('writes an email whose subject is the chosen topic', async () => {
    const user = userEvent.setup()
    await openContact(language)
    const topics = screen.getByRole('group', { name: page.topicGroup })
    const send = screen.getByRole('link', { name: page.send })
    // The first topic is chosen on arrival.
    expect(send).toHaveAttribute('href', page.topics[0]?.href)
    for (const { button, href } of [...page.topics].reverse()) {
      await user.click(within(topics).getByRole('button', { name: button }))
      expect(within(topics).getByRole('button', { name: button })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      expect(send).toHaveAttribute('href', href)
    }
  })

  it('marks every unknown as a placeholder', async () => {
    await openContact(language)
    const main = screen.getByRole('main')
    expect(unmarkedPlaceholders(main)).toEqual([])
    expect(markedPlaceholders(main)).toEqual(page.placeholders)
  })

  it('has no detectable accessibility violations', async () => {
    const { container } = await openContact(language)
    // jsdom cannot paint, so colour contrast is checked in the browser.
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})

describe.each(['en', 'de'] as const)('the contact page copy (%s)', (language) => {
  it('shows every line of the reviewed copy', async () => {
    await openContact(language)
    const main = screen.getByRole('main')
    for (const line of COPY[language]) expect(main).toHaveTextContent(line)
  })
})
