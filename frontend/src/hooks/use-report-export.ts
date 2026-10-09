import { useMutation, type UseMutationResult } from '@tanstack/react-query'

import {
  exportInventoryReport,
  exportResultReport,
  type InventoryReportRequest,
  type InventoryTool as ReportTool,
  type ResultReportRequest,
} from '@/api'
import type { Language } from '@/i18n'
import type { InventoryTool } from '@/lib/inventory'

import { documentFailure, fileOf, saveFile, type DocumentFailure } from './use-document-drafts'

/** The message for each refusal; a report has no checks to fail, so that refusal reads as any
 *  other failure. */
const REPORT_FAILURE_KEYS = {
  'checks-failed': 'report.failed',
  'too-large': 'report.tooLong',
  busy: 'documents.download.busy',
  'timed-out': 'report.timedOut',
  failed: 'report.failed',
} as const satisfies Record<DocumentFailure, string>

/** The i18n key of the message for a failed report. */
export function reportFailureKey(error: unknown): (typeof REPORT_FAILURE_KEYS)[DocumentFailure] {
  return REPORT_FAILURE_KEYS[documentFailure(error)]
}

/** A result's report file: the tool id names it, the report ID is inside. The API names it
 *  `klar-report.pdf` only as a fallback; this is the name it is saved under. */
export function resultReportFileName(
  toolId: string,
  format: ResultReportRequest['format'],
): string {
  return `klar-report-${toolId}.${format}`
}

/** The report for a lawyer (P25): the API makes it from the posted result, in the screen's
 *  language, and the browser saves it. One click is one request; nothing is sent again by
 *  itself. */
export function useExportResultReport(
  toolId: string,
): UseMutationResult<void, Error, ResultReportRequest> {
  return useMutation({
    retry: false,
    mutationFn: async (request: ResultReportRequest) => {
      const file = fileOf(await exportResultReport({ body: request, parseAs: 'blob' }))
      saveFile(file, resultReportFileName(toolId, request.format))
    },
  })
}

/** One tool as the inventory report lists it: its latest result's class, status, roles, law
 *  version and date, and each duty's short label in `language`. A tool without a result Klar can
 *  read, or with no class, is listed as not classified yet. */
export function reportTool(tool: InventoryTool, language: Language): ReportTool {
  const { result } = tool
  if (!result || result.risk_class === null) return { name: tool.name, duties: [] }
  return {
    name: tool.name,
    risk_class: result.risk_class,
    status: result.status,
    role: result.role ?? null,
    also_role: result.also_role ?? null,
    law_version: result.law_version,
    as_of: result.as_of,
    duties: (result.obligations ?? []).map((duty) => ({
      label: language === 'de' ? duty.label_de : duty.label_en,
      article: duty.article,
      applies_from: duty.applies_from,
      legacy: duty.legacy ?? null,
    })),
  }
}

/** The inventory report (Your data, "Report (PDF)"): every tool with its class and duties, made
 *  by the API and saved by the browser. */
export function useExportInventoryReport(): UseMutationResult<void, Error, InventoryReportRequest> {
  return useMutation({
    retry: false,
    mutationFn: async (request: InventoryReportRequest) => {
      const file = fileOf(await exportInventoryReport({ body: request, parseAs: 'blob' }))
      saveFile(file, `klar-inventory-report.${request.format}`)
    },
  })
}
