import { useNavigate } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'
import { ScreenTitle } from '@/components/ScreenTitle'
import type { InventoryTool } from '@/lib/inventory'

import { saveDraft } from './classification-store'
import { toolName } from './result-text'

/**
 * A tool in the inventory with no result to show: it was never checked (a tool restored from a
 * file without its runs), or its saved result can't be read. "Classify this tool" opens Classify
 * with its name and description in the form; nothing runs until the user starts the checks.
 */
export function ToolWithoutResult({ tool }: { tool: InventoryTool }): JSX.Element {
  const { t } = useTranslation()
  const navigate = useNavigate()

  function classify(): void {
    saveDraft({ name: tool.name ?? '', description: tool.description })
    void navigate({ to: '/app/classify' })
  }

  return (
    <>
      <ScreenTitle className="break-words">{toolName(t, tool.name)}</ScreenTitle>
      <GlassPanel className="flex flex-col items-start gap-4">
        <p className="m-0 text-body text-slate">
          {tool.hasUnreadableResult ? t('result.unreadable.body') : t('result.unchecked.body')}
        </p>
        <Button onClick={classify}>{t('result.withoutResult.action')}</Button>
      </GlassPanel>
    </>
  )
}
