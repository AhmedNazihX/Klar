import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Reveal } from '@/components/Reveal'
import { Typewriter, type TypewriterLine } from '@/components/Typewriter'

import { CLASSIFY_EXAMPLE, type ExampleLine } from './classify-example'
import { SectionTitle } from './SectionTitle'

const MCP_TOOLS = ['search_ai_act', 'get_provision', 'list_obligations', 'classify_system'] as const

// The code colours on glass-dark (site-motion.css › code panel): the class highlighted, the other
// values, and the trimmed parts.
const VALUE_CLASS = 'text-(--code-value)'
const HIGHLIGHT_CLASS = 'text-(--code-highlight)'
const TRIMMED_CLASS = 'text-(--code-comment)'

/** One key's line, inside the braces: `"key": value,` with the value coloured. */
function keyLine(
  line: ExampleLine,
  isLast: boolean,
  words: (key: 'steps' | 'disclaimer') => string,
): ReactNode {
  const comma = isLast ? '' : ','
  let value: ReactNode
  if ('value' in line) {
    value = (
      <span className={line.highlight ? HIGHLIGHT_CLASS : VALUE_CLASS}>
        &quot;{line.value}&quot;
      </span>
    )
  } else if ('object' in line) {
    const fields = Object.entries(line.object).map(([key, text]) => (
      <span key={key}>
        &quot;{key}&quot;: <span className={VALUE_CLASS}>&quot;{text}&quot;</span>
      </span>
    ))
    value = (
      <>
        {'{ '}
        {fields}
        <span className={TRIMMED_CLASS}>, …</span>
        {' }'}
      </>
    )
  } else if (line.trimmed === 'steps') {
    value = (
      <>
        [ <span className={TRIMMED_CLASS}>{words('steps')}</span> ]
      </>
    )
  } else {
    value = <span className={VALUE_CLASS}>&quot;{words('disclaimer')}&quot;</span>
  }
  return (
    <>
      &quot;{line.key}&quot;: {value}
      {comma}
    </>
  )
}

/**
 * "Your other AI agents can ask it too.": the four MCP tools, and a classify_system result on
 * glass-dark that types itself out (Typewriter) with the API's real field names.
 */
export function AgentsSection(): JSX.Element {
  const { t } = useTranslation()
  const words = (key: 'steps' | 'disclaimer'): string => t(`landing.agents.${key}`)
  const lines: TypewriterLine[] = [
    {
      id: 'title',
      content: <span className={TRIMMED_CLASS}>classify_system → result</span>,
    },
    { id: 'open', content: '{' },
    ...CLASSIFY_EXAMPLE.map((line, index) => ({
      id: line.key,
      indent: true,
      content: keyLine(line, index === CLASSIFY_EXAMPLE.length - 1, words),
    })),
    { id: 'close', content: '}' },
  ]

  return (
    <section
      id="agents"
      aria-labelledby="agents-title"
      className="mt-32 flex scroll-mt-28 flex-col gap-10 lg:flex-row lg:items-center lg:gap-12"
    >
      <div className="flex flex-col gap-4.5 lg:w-[460px] lg:shrink-0">
        <SectionTitle id="agents-title" size="medium">
          {t('landing.agents.title')}
        </SectionTitle>
        <p className="text-body leading-[1.6] text-slate">{t('landing.agents.lead')}</p>
        <dl className="m-0 grid grid-cols-1 gap-x-5 gap-y-3 text-body-small sm:grid-cols-2">
          {MCP_TOOLS.map((tool) => (
            <div key={tool} className="flex flex-col gap-0.5">
              <dt className="font-semibold">{tool}</dt>
              <dd className="m-0 text-label font-normal text-slate">
                {t(`landing.agents.tools.${tool}`)}
              </dd>
            </div>
          ))}
        </dl>
      </div>
      <Reveal className="min-w-0 flex-1">
        <Typewriter
          label={t('landing.agents.codeLabel')}
          lines={lines}
          className="code-panel rounded-card px-6 py-7 glass-dark sm:px-8"
        />
      </Reveal>
    </section>
  )
}
