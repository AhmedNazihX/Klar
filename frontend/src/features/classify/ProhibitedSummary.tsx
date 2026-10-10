import type { JSX, ReactNode } from 'react'

import type { ClassificationRun } from './classification-store'
import { FactsPanel } from './FactsPanel'
import { FineTile } from './FineTile'
import { ProhibitedVerdict } from './ProhibitedVerdict'
import { StepsPanel } from './StepsPanel'
import { WhatToDoNow } from './WhatToDoNow'
import { WhyChecksStopped } from './WhyChecksStopped'

/** The summary of a decided ban (artboard `ResultProhibited`), under the result's title row:
 *  the verdict with the date it has been banned since; what to do now, the maximum fine and why
 *  the checks stopped, beside the facts it rests on; then how Klar got there, the steps after
 *  Art. 5 not checked. No duty list: there's no route to comply. Returns a fragment, so its
 *  panels stay the screen's direct children (load motion). */
export function ProhibitedSummary({
  run,
  note,
  onChangeFacts,
  onConfirmFact,
  isBusy,
  onExpandAll,
}: {
  run: ClassificationRun
  /** Under the verdict: what the original text's run found (OriginalTextNote). */
  note?: ReactNode
  /** Reopens the description. */
  onChangeFacts: () => void
  /** Confirms an assumed fact, which runs the checks again (P5b). */
  onConfirmFact: (fact: string) => void
  /** True while that run is going. */
  isBusy: boolean
  /** Opens the reviewer view. */
  onExpandAll: () => void
}): JSX.Element {
  const { result } = run
  return (
    <>
      <ProhibitedVerdict result={result} today={new Date()} />
      {note}
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        <div className="flex min-w-0 flex-1 flex-col gap-5">
          <WhatToDoNow toolId={run.toolId} toolName={run.name} result={result} />
          <FineTile result={result} />
          <WhyChecksStopped result={result} />
        </div>
        <FactsPanel
          result={result}
          onChange={onChangeFacts}
          onConfirm={onConfirmFact}
          isBusy={isBusy}
        />
      </div>
      <StepsPanel result={result} onExpandAll={onExpandAll} />
    </>
  )
}
