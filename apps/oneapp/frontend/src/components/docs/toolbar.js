/**
 * The row of controls over a whole document.
 *
 * frappe-ui ships three presets and `articleToolbar` is the closest, but it is
 * built for a *field* — a description box inside a form, where the surrounding
 * page carries the undo, the alignment and the colour. A document has no
 * surrounding page: this row is the only chrome there is, so it carries the
 * things a person writing a scope of works reaches for and a person filling in
 * a description does not.
 *
 * Composed from frappe-ui's own items rather than written as buttons. A menu
 * item knows its own icon, its own active state and its own command; a
 * hand-drawn button knows none of that and goes stale the first time the
 * extension list changes. What decides membership is `RichTextKit`: every item
 * here runs a command one of its extensions registers, because a control whose
 * extension is not loaded is a button that does nothing.
 */

import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Blockquote,
  Bold,
  BulletList,
  FontColor,
  FontHighlight,
  HeadingGroup,
  HorizontalRule,
  InlineCode,
  InsertImage,
  InsertLink,
  InsertTable,
  Italic,
  OrderedList,
  Redo,
  Separator,
  Strike,
  Undo,
} from '@/ui'

export const documentToolbar = [
  Undo,
  Redo,
  Separator,
  HeadingGroup,
  Separator,
  Bold,
  Italic,
  Strike,
  InlineCode,
  FontColor,
  FontHighlight,
  Separator,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Separator,
  BulletList,
  OrderedList,
  Blockquote,
  Separator,
  InsertLink,
  InsertImage,
  InsertTable,
  HorizontalRule,
]

/** How wide the page is, and what a line of it looks like. */
export const WIDTHS = {
  page: { label: 'Page', class: 'max-w-[48rem]' },
  wide: { label: 'Wide', class: 'max-w-[64rem]' },
  full: { label: 'Full width', class: 'max-w-none' },
}

export const FONTS = {
  '': { label: 'Default', class: '' },
  serif: { label: 'Serif', class: 'font-serif' },
  mono: { label: 'Monospace', class: 'font-mono' },
}

export const SPACINGS = {
  tight: { label: 'Tight', class: 'leading-snug' },
  normal: { label: 'Normal', class: 'leading-relaxed' },
  loose: { label: 'Loose', class: 'leading-loose' },
}

/** The three settings as one list of classes, for the element that draws them. */
export function pageClasses(settings = {}) {
  return [
    WIDTHS[settings.width]?.class ?? WIDTHS.page.class,
    FONTS[settings.font]?.class ?? '',
    SPACINGS[settings.spacing]?.class ?? SPACINGS.normal.class,
  ]
}
