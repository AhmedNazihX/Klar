import type { JSX } from 'react'

import { AccuracySection } from './AccuracySection'
import { AgentsSection } from './AgentsSection'
import { ChecksSection } from './ChecksSection'
import { CtaBand } from './CtaBand'
import { DatesTimeline } from './DatesTimeline'
import { FeaturesSection } from './FeaturesSection'
import { Hero } from './Hero'
import { UncertaintySection } from './UncertaintySection'

/**
 * The landing page, English at `/` and German at `/de` (artboards `Main` and `MainDE`): the hero,
 * the dates, the four checks, the two honest outcomes, the features, the accuracy figures, the
 * agent example and the closing band, 96 px after the hero and 128 px between sections. The site
 * frame adds the nav, the moving ground and the footer.
 */
export function LandingPage(): JSX.Element {
  return (
    <div className="flex min-w-0 flex-col">
      <Hero />
      <DatesTimeline />
      <ChecksSection />
      <UncertaintySection />
      <FeaturesSection />
      <AccuracySection />
      <AgentsSection />
      <CtaBand />
    </div>
  )
}
