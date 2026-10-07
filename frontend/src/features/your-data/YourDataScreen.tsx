import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { ScreenTitle } from '@/components/ScreenTitle'
import { useDeleteUserData } from '@/hooks/use-delete-user-data'

import { DeletedPanel } from './DeletedPanel'
import { DeletePanel } from './DeletePanel'
import { DownloadPanel } from './DownloadPanel'
import { KeptDataPanel } from './KeptDataPanel'
import { ProcessorsPanel } from './ProcessorsPanel'

/**
 * Your data (artboard `YourData`): what Klar keeps and who processes it, then Download
 * everything (with Import) and Delete my data, two by two (one column on a phone). A deletion
 * ends at "Your data is deleted" in place of the four panels.
 */
export function YourDataScreen(): JSX.Element {
  const { t } = useTranslation()
  // Held here, so the outcome survives the delete panel and its dialog going away.
  const deletion = useDeleteUserData()
  return (
    <>
      <div className="flex max-w-[760px] flex-col gap-1.5">
        <ScreenTitle>{t('screen.yourData')}</ScreenTitle>
        <p className="m-0 text-body text-slate">{t('yourData.intro')}</p>
      </div>
      {deletion.isSuccess ? (
        <DeletedPanel />
      ) : (
        <div className="grid min-w-0 grid-cols-1 gap-5 lg:grid-cols-2">
          <KeptDataPanel />
          <ProcessorsPanel />
          <DownloadPanel />
          <DeletePanel deletion={deletion} />
        </div>
      )}
    </>
  )
}
