import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { useLawVersion } from '@/hooks/use-law-version'
import type { CompanyProfile } from '@/lib/company-profile'

/** The sidebar's second line: staff band and size class when known, otherwise what there is. */
function useDetailLine(company: CompanyProfile | null): string {
  const { t } = useTranslation()
  const law = useLawVersion()
  if (!company) return t('sidebar.companyEmpty')
  if (company.staffBand === null) return t('sidebar.companySaved')
  const band = t(`welcome.staffBand.${company.staffBand}`)
  if (company.sizeClass === 'sme') return t('sidebar.companyLine.sme', { band })
  // Small mid-caps exist only in the amended text.
  if (company.sizeClass === 'smc' && law === 'amended') {
    return t('sidebar.companyLine.smc', { band })
  }
  return t('sidebar.companyStaff', { band })
}

/**
 * The sidebar's company card, filled from the profile (artboard: "Nordwerk Logistik GmbH / 40
 * staff, counts as an SME"). It opens the Welcome screen, where the profile is edited.
 */
export function CompanyLine({ company }: { company: CompanyProfile | null }): JSX.Element {
  const { t } = useTranslation()
  const detail = useDetailLine(company)
  return (
    <Link
      to="/app/welcome"
      title={t('sidebar.companyEdit')}
      className="flex flex-col gap-1 rounded-[18px] px-4 py-3.5 no-underline glass-thin hover:bg-white/45"
    >
      <span className="text-label font-semibold break-words text-ink">
        {company?.companyName ?? t('sidebar.companyName')}
      </span>
      <span className="text-caption font-normal text-slate">{detail}</span>
    </Link>
  )
}
