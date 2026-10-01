import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

const LINK_CLASS = 'text-label font-medium text-ink no-underline hover:text-lens-blue'

/**
 * The end of every public page (components.md › SiteFooter): the guidance notice in bold, that
 * Klar is an AI system, how data is handled (the processors and the 30-day deletion, decision 013)
 * and the four site pages.
 */
export function SiteFooter(): JSX.Element {
  const { t } = useTranslation()
  return (
    <footer className="mt-24 flex flex-col justify-between gap-8 text-label font-normal md:mt-32 md:flex-row md:gap-12">
      <div className="flex max-w-[620px] flex-col gap-2">
        <p className="font-semibold text-ink">{t('site.footer.guidance')}</p>
        <p className="text-slate">{t('site.footer.data')}</p>
      </div>
      <nav aria-label={t('site.footer.linksLabel')}>
        <ul className="m-0 flex list-none flex-wrap gap-x-7 gap-y-2 p-0">
          <li>
            <Link to="/method" className={LINK_CLASS}>
              {t('site.footer.method')}
            </Link>
          </li>
          <li>
            <Link to="/privacy" className={LINK_CLASS}>
              {t('site.footer.privacy')}
            </Link>
          </li>
          <li>
            <Link to="/impressum" lang="de" className={LINK_CLASS}>
              {t('site.footer.impressum')}
            </Link>
          </li>
          <li>
            <Link to="/contact" className={LINK_CLASS}>
              {t('site.footer.contact')}
            </Link>
          </li>
        </ul>
      </nav>
    </footer>
  )
}
