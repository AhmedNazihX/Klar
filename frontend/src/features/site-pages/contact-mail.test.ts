import { describe, expect, it } from 'vitest'

import { CONTACT_ADDRESS, contactMailto } from './contact-mail'

describe('contactMailto', () => {
  it('fills in the subject, encoded, and leaves the recipient empty while there is no address', () => {
    expect(contactMailto(null, 'Klar: privacy request')).toBe(
      'mailto:?subject=Klar%3A%20privacy%20request',
    )
  })

  it('addresses the email once an address is set', () => {
    expect(contactMailto('hello@example.org', 'Klar: feedback')).toBe(
      'mailto:hello@example.org?subject=Klar%3A%20feedback',
    )
  })

  it('keeps a subject with & or ? from adding fields of its own', () => {
    expect(contactMailto(null, 'Fragen & Antworten?')).toBe(
      'mailto:?subject=Fragen%20%26%20Antworten%3F',
    )
  })

  it('has no address yet, so the page shows a placeholder', () => {
    expect(CONTACT_ADDRESS).toBeNull()
  })
})
