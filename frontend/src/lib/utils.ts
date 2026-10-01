import { createCn } from 'cn/config'

// The design system's type scale (index.css › --text-*). Without it, class merging would read
// `text-micro` as a colour and drop it next to `text-slate`. utils.test.ts checks it against tokens.json.
export const TYPE_SCALE = [
  'display-hero',
  'display-section',
  'heading-page',
  'heading-panel',
  'heading-small',
  'body-large',
  'body',
  'body-small',
  'label',
  'caption',
  'micro',
  'verdict',
  'verdict-small',
  'document-title',
  'quote',
  'quote-small',
  'code',
]

export const cn = createCn({ extend: { classGroups: { 'font-size': [{ text: TYPE_SCALE }] } } })
