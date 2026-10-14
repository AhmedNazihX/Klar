import { http, HttpResponse } from 'msw'

import type { Obligation, ObligationList } from '@/api'
import type { ReliefNotes, ReliefTable } from '@/hooks/use-relief-notes'
import { env } from '@/lib/env'

export const OBLIGATIONS_URL = `${env.apiUrl}/obligations`

/** The relief notes of the committed obligations table (`supabase/seed/obligations.yaml`): its
 *  two entries with one, both a high-risk provider's. */
export const TABLE_RELIEF: ReliefTable = {
  'hr-provider-qms': {
    relief_note:
      'The quality management system may be proportionate to the size of the organisation for SMEs, including start-ups, and SMCs (Art. 17(2)). SMEs without partner or linked enterprises may comply with certain elements in a simplified manner (Art. 63(1)).',
    relief_note_de:
      'Für KMU, einschließlich Start-up-Unternehmen, und kleine Midcap-Unternehmen kann das Qualitätsmanagementsystem in einem angemessenen Verhältnis zur Größe der Organisation stehen (Art. 17 Abs. 2). KMU ohne Partnerunternehmen oder verbundene Unternehmen können bestimmte Elemente in vereinfachter Weise einhalten (Art. 63 Abs. 1).',
  },
  'hr-provider-technical-documentation': {
    relief_note:
      "SMEs, including start-ups, and SMCs may provide the Annex IV elements in a simplified manner, using the Commission's simplified form (Art. 11(1)). As of 24 September 2026 the form did not appear to be published.",
    relief_note_de:
      'KMU, einschließlich Start-up-Unternehmen, und kleine Midcap-Unternehmen können die Angaben nach Anhang IV in vereinfachter Weise bereitstellen, mit dem vereinfachten Formular der Kommission (Art. 11 Abs. 1). Am 24. September 2026 schien das Formular noch nicht veröffentlicht zu sein.',
  },
}

/** A table row for `key` with `notes`; the other fields are placeholders the relief lookup
 *  doesn't read. */
function tableRow(key: string, notes: ReliefNotes): Obligation {
  return {
    key,
    duty: 'A duty.',
    duty_de: 'Eine Pflicht.',
    label_en: 'A duty',
    label_de: 'Eine Pflicht',
    article: 'art:17:1',
    applies_from: '2026-08-02',
    ...notes,
  }
}

/** `GET /obligations` answering every role and class with a row for each of `table`'s keys,
 *  noting each lookup as `role/risk_class` in `asked`. */
export function obligationsTableHandler(table: ReliefTable = TABLE_RELIEF, asked: string[] = []) {
  return http.get(OBLIGATIONS_URL, ({ request }) => {
    const query = new URL(request.url).searchParams
    asked.push(`${query.get('role') ?? ''}/${query.get('risk_class') ?? ''}`)
    const list: ObligationList = {
      law_version: 'amended',
      obligations: Object.entries(table).map(([key, notes]) => tableRow(key, notes)),
      disclaimer: 'x',
    }
    return HttpResponse.json(list)
  })
}
