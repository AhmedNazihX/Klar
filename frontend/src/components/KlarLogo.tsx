import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

// Logo artwork from the Brand board (project/Brand.dc.html). The colours are part of the mark, not
// theme tokens, so they stay literal here. The symbol is a speech bubble of three glass layers,
// ink to Lens blue to clear; the wordmark is Lexend, outlined.
const OUTER =
  'M0 250 C0 190 38 152 108 134 L700 12 C846 -16 950 58 950 200 V680 C950 748 914 794 866 810 L867 810 V972 C867 998 846 1006 822 992 C738 934 650 880 560 880 H150 C60 880 0 822 0 736 Z'
const LAYER_TOP =
  'M0 469 V250 C0 190 38 152 108 134 L700 12 C846 -16 950 58 950 200 V336 C918 300 870 278 800 278 C690 278 560 366 420 438 C250 522 92 519 0 469 Z'
const LAYER_MIDDLE =
  'M0 455 C92 505 250 508 420 424 C560 352 690 264 800 264 C870 264 918 286 950 322 V680 C950 748 914 794 866 810 L853 806 V656 C853 576 832 520 760 522 C640 524 530 600 400 656 C232 728 82 717 0 669 Z'
const LAYER_BOTTOM =
  'M0 655 C82 703 232 714 400 642 C530 586 640 510 760 508 C832 506 867 562 867 642 V972 C867 998 846 1006 822 992 C738 934 650 880 560 880 H150 C60 880 0 822 0 736 Z'
const SEPARATOR_TOP =
  'M0 455 C92 505 250 508 420 424 C560 352 690 264 800 264 C870 264 918 286 950 322'
const SEPARATOR_BOTTOM =
  'M0 655 C82 703 232 714 400 642 C530 586 640 510 760 508 C832 506 867 562 867 642 V812'
const WORDMARK = [
  'M204.3 493.1 172.3 356.9 526.1 0H708.1ZM91 700V0H241V700ZM545.3 700 282.7 352.5 386.1 263.3 723.1 700Z',
  'M813.4 700V0H955.3V700Z',
  'M1316.9 709.6Q1251.2 709.6 1198.2 673.8Q1145.3 638 1114.1 575.8Q1082.9 513.6 1082.9 434.4Q1082.9 354.3 1114.2 292.4Q1145.6 230.5 1199.9 195.3Q1254.2 160.1 1323.2 160.1Q1362.3 160.1 1394.7 171.3Q1427.2 182.6 1451.7 202.7Q1476.2 222.8 1492.9 249.1Q1509.6 275.3 1516.7 305.4L1486.7 300.1V171.1H1627.7V700H1484.8V572.7L1516.9 569.9Q1509.4 597.7 1491.3 623Q1473.2 648.3 1446.4 667.6Q1419.7 686.8 1386.9 698.2Q1354.2 709.6 1316.9 709.6ZM1356 587.4Q1396 587.4 1426 568.3Q1455.9 549.2 1472.6 514.7Q1489.2 480.2 1489.2 434.4Q1489.2 389.3 1472.6 354.9Q1455.9 320.6 1426 301.4Q1396 282.3 1356 282.3Q1316.6 282.3 1287.1 301.4Q1257.7 320.6 1241.1 354.9Q1224.4 389.3 1224.4 434.4Q1224.4 480.2 1241.1 514.7Q1257.7 549.2 1287.1 568.3Q1316.6 587.4 1356 587.4Z',
  'M1780.2 700V171.1H1916.9L1921.6 341.2L1897.9 305.8Q1909.7 264.7 1936.8 231.6Q1963.9 198.4 2000.3 179.3Q2036.8 160.1 2076.9 160.1Q2094.3 160.1 2110 162.9Q2125.7 165.7 2137 169.7L2098.7 325.7Q2087.5 319.9 2070.3 315.4Q2053.1 310.9 2034.8 310.9Q2011.3 310.9 1990.7 319.5Q1970.1 328.1 1955.1 343.6Q1940.1 359.2 1931.4 380Q1922.7 400.8 1922.7 426.3V700Z',
]

const TONES = {
  light: { top: ['#2A4FD0', '#15245A', '#0F1B2D'], glow: 0.32, word: '#0F1B2D' },
  dark: { top: ['#3A5EE8', '#22357A', '#1A2A52'], glow: 0.5, word: '#F4F7FC' },
} as const

export type KlarLogoProps = {
  /** `full` is symbol and wordmark; `symbol` is the speech bubble alone. */
  variant?: 'full' | 'symbol'
  /** The background the logo sits on. */
  tone?: 'light' | 'dark'
  className?: string
}

/** The Klar logo. It is labelled "Klar" for assistive technology. */
export function KlarLogo({
  variant = 'full',
  tone = 'light',
  className,
}: KlarLogoProps): JSX.Element {
  const { t } = useTranslation()
  // SVG ids are document-global, so each instance gets its own.
  const id = `klar${useId().replace(/[^a-zA-Z0-9]/g, '')}`
  const colours = TONES[tone]
  const viewBox = variant === 'full' ? '0 -290 3452.9 1182' : '0 -290 1150 1182'
  return (
    <svg
      viewBox={viewBox}
      role="img"
      aria-label={t('app.name')}
      className={className}
      style={{ overflow: 'visible' }}
    >
      <defs>
        <linearGradient
          id={`${id}-top`}
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="700"
          x2="950"
          y2="0"
        >
          <stop offset="0" stopColor={colours.top[0]} />
          <stop offset=".45" stopColor={colours.top[1]} />
          <stop offset="1" stopColor={colours.top[2]} />
        </linearGradient>
        <linearGradient
          id={`${id}-blue`}
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="0"
          x2="950"
          y2="0"
        >
          <stop offset="0" stopColor="#7896FF" />
          <stop offset=".5" stopColor="#2D4BE0" />
          <stop offset="1" stopColor="#2944D2" />
        </linearGradient>
        <linearGradient
          id={`${id}-pale`}
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="560"
          x2="870"
          y2="1000"
        >
          <stop offset="0" stopColor="#FFFFFF" />
          <stop offset=".55" stopColor="#E8EFFF" />
          <stop offset="1" stopColor="#C3D4FF" />
        </linearGradient>
        <linearGradient
          id={`${id}-sep`}
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="0"
          x2="950"
          y2="0"
        >
          <stop offset="0" stopColor="#FFFFFF" stopOpacity=".5" />
          <stop offset=".3" stopColor="#FFFFFF" stopOpacity=".95" />
          <stop offset=".8" stopColor="#FFFFFF" stopOpacity=".9" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity=".4" />
        </linearGradient>
        <filter
          id={`${id}-glow`}
          filterUnits="userSpaceOnUse"
          x="-400"
          y="400"
          width="1750"
          height="1000"
        >
          <feGaussianBlur stdDeviation="48" />
        </filter>
        <clipPath id={`${id}-outer`} clipPathUnits="userSpaceOnUse">
          <path d={OUTER} />
        </clipPath>
      </defs>
      <g transform="translate(0 -280) scale(1.162)">
        <ellipse
          cx="450"
          cy="840"
          rx="360"
          ry="80"
          fill="#2D4BE0"
          fillOpacity={colours.glow}
          filter={`url(#${id}-glow)`}
        />
        <path d={LAYER_TOP} fill={`url(#${id}-top)`} />
        <path d={LAYER_MIDDLE} fill={`url(#${id}-blue)`} />
        <path d={LAYER_BOTTOM} fill={`url(#${id}-pale)`} />
        <g
          clipPath={`url(#${id}-outer)`}
          fill="none"
          strokeWidth="3.5"
          strokeLinejoin="round"
          stroke={`url(#${id}-sep)`}
        >
          <path d={SEPARATOR_TOP} />
          <path d={SEPARATOR_BOTTOM} />
        </g>
      </g>
      {variant === 'full' && (
        <g
          transform="translate(1307.9 0)"
          fill={colours.word}
          stroke={colours.word}
          strokeWidth="16"
          strokeLinejoin="round"
        >
          {WORDMARK.map((d) => (
            <path key={d} d={d} />
          ))}
        </g>
      )}
    </svg>
  )
}
