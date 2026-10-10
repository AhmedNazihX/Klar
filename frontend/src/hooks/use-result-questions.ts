import { resultThread } from '@/features/ask/qa-history'
import { runNumber, type ClassificationRun } from '@/features/classify/classification-store'

import { useQaThread, type QaThread } from './use-qa-thread'

/** The questions-about-this-result thread of one run (P7), keyed by its tool and run number, so
 *  the next run starts afresh. The result screen holds it above its view switch, so a question
 *  asked in one view is answered in the thread the other view shows. */
export function useResultQuestions(run: ClassificationRun): QaThread {
  const { result } = run
  return useQaThread(resultThread(run.toolId, runNumber(run)), {
    lawVersion: result.law_version,
    result,
  })
}
