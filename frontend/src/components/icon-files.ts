import add from './icons/add.svg'
import alert from './icons/alert.svg'
import ask from './icons/ask.svg'
import check from './icons/check.svg'
import chevronDown from './icons/chevron-down.svg'
import classify from './icons/classify.svg'
import documents from './icons/documents.svg'
import info from './icons/info.svg'
import inventory from './icons/inventory.svg'
import obligations from './icons/obligations.svg'
import privacy from './icons/privacy.svg'
import send from './icons/send.svg'

/**
 * The design system's Icons asset group (24 px grid, round caps and joins, drawn in ink), copied
 * as files from the Klar artifact and never redrawn. Keys are the system's `IconName`s.
 */
export const ICON_FILES = {
  inventory,
  classify,
  obligations,
  documents,
  ask,
  add,
  privacy,
  check,
  info,
  'chevron-down': chevronDown,
  send,
  alert,
} as const

export type IconName = keyof typeof ICON_FILES
export const ICON_NAMES = Object.keys(ICON_FILES) as IconName[]
