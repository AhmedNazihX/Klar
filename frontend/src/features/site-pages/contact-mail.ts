// The Contact page has no form backend (decision 026 item 5): a `mailto:` link whose subject names
// the topic. The address is still to be decided, so it is null and the page shows a marked
// placeholder; set it here before launch.

/** The address the Contact page writes to; null until it is decided. */
export const CONTACT_ADDRESS: string | null = null

export const CONTACT_TOPICS = ['question', 'feedback', 'privacy'] as const
export type ContactTopic = (typeof CONTACT_TOPICS)[number]

/**
 * A `mailto:` URL with `subject` filled in (RFC 6068). With no address the recipient is left
 * empty, so the email program still opens with the subject.
 */
export function contactMailto(address: string | null, subject: string): string {
  const to = address === null ? '' : encodeURIComponent(address).replace('%40', '@')
  return `mailto:${to}?subject=${encodeURIComponent(subject)}`
}
