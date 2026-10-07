import { describe, expect, it } from 'vitest'

import { findPersonalData } from './personal-data'

describe('findPersonalData', () => {
  it.each([
    ['an English email address', 'Applicants write to anna.schmidt@example.com first.', 'email'],
    ['a German email address', 'Rückfragen gehen an bewerbung@nordwerk-logistik.de.', 'email'],
    ['an international phone number', 'Call the recruiter on +49 30 1234 5678.', 'phone'],
    ['a German landline', 'Die Hotline 030/1234567 nimmt Beschwerden an.', 'phone'],
    ['a German mobile number', 'Erreichbar unter 0170 1234567.', 'phone'],
    ['a North American number', 'Support is at (555) 123-4567 during office hours.', 'phone'],
    ['a spaced IBAN', 'Salaries go to DE89 3704 0044 0532 0130 00 each month.', 'iban'],
    ['an unspaced IBAN', 'Gehalt auf GB82WEST12345698765432 überwiesen.', 'iban'],
    ['an English title and surname', 'Mr. Jones reviews every ranking.', 'name'],
    [
      'a German title and surname',
      'Die Liste prüft Frau Müller aus der Personalabteilung.',
      'name',
    ],
    ['a common first name and surname', 'The tool flagged Sarah Becker as a weak fit.', 'name'],
    ['a German first name and surname', 'Das System hat Jürgen Weber abgelehnt.', 'name'],
  ] as const)('finds %s', (_, text, kind) => {
    expect(findPersonalData(text)).toEqual([kind])
  })

  it('lists every kind found, in a fixed order', () => {
    const text =
      'Frau Schulz (schulz@example.de, 0170 1234567) is paid to DE89 3704 0044 0532 0130 00.'
    expect(findPersonalData(text)).toEqual(['email', 'phone', 'iban', 'name'])
  })

  it.each([
    [
      'a description without personal data',
      'We use an AI tool that ranks job applicants by their CV and suggests who to interview. A ' +
        'recruiter reviews the shortlist before anyone is invited.',
    ],
    [
      'a German description without personal data',
      'Wir setzen eine KI ein, die Bewerbungen nach dem Lebenslauf sortiert. Die Frau Mitte 30 ' +
        'aus dem Beispiel ist erfunden; eine Personalerin prüft jede Liste.',
    ],
    ['dates', 'Rolled out on 01/10/2026 and reviewed on 07-10-2026 and 01.08.2026.'],
    ['amounts and years', 'Turnover of +1 000 000 EUR in 2026, 250 staff, 0.5 FTE.'],
    ['legal references', 'Annex III point 4(a), Art. 6(3) and CELEX 02024R1689-20260727.'],
    ['an invalid IBAN-like code', 'Order number DE00 1234 5678 9012 3456 78 was shipped.'],
    ['a product name', 'Built on Microsoft Copilot and the Adam Optimizer.'],
  ])('ignores %s', (_, text) => {
    expect(findPersonalData(text)).toEqual([])
  })
})
