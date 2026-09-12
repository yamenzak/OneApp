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
import { __ } from '@/shared/lib/runtime/translate'

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

/**
 * The same row, for a document with other people in it.
 *
 * One difference and it is not cosmetic. Collaboration replaces the editor's
 * undo with its own — undo has to be *this person's* last edit, not the last
 * thing that happened, or pressing it takes back a colleague's sentence — and
 * that undo reads a ProseMirror plugin that only exists once the view has
 * mounted. frappe-ui builds the editor with `element: null` and lets
 * `<EditorContent>` mount it a tick later, so for that tick the toolbar asks
 * a button whether it is disabled and the answer throws.
 *
 * Nothing is broken by it — undo works the moment there is anything to undo —
 * but a `TypeError` on the console every time somebody opens a document is
 * not something to leave lying there, and it is the kind of thing a guard is
 * right to fail on. So the question is asked safely: an undo that cannot yet
 * say is a button that is not yet enabled.
 */
function guarded(item) {
  return {
    ...item,
    isDisabled: (editor) => {
      try {
        return item.isDisabled(editor)
      } catch {
        return true
      }
    },
  }
}

export const liveDocumentToolbar = documentToolbar.map(
  (one) => (one === Undo || one === Redo ? guarded(one) : one),
)

/** How wide the page is, and what a line of it looks like. */
export const WIDTHS = {
  page: { label: __('Page'), class: 'max-w-page' },
  wide: { label: __('Wide'), class: 'max-w-[64rem]' },
  full: { label: __('Full width'), class: 'max-w-none' },
}

export const FONTS = {
  '': { label: __('Default'), class: '' },
  serif: { label: __('Serif'), class: 'font-serif' },
  mono: { label: __('Monospace'), class: 'font-mono' },
}

export const SPACINGS = {
  tight: { label: __('Tight'), class: 'leading-snug' },
  normal: { label: __('Normal'), class: 'leading-relaxed' },
  loose: { label: __('Loose'), class: 'leading-loose' },
}

/** Face and leading — the two that hold whether there are pages or not. */
export function bodyClasses(settings = {}) {
  return [
    FONTS[settings.font]?.class ?? '',
    SPACINGS[settings.spacing]?.class ?? SPACINGS.normal.class,
  ]
}

/** The three settings as one list of classes, for the element that draws them. */
export function pageClasses(settings = {}) {
  return [WIDTHS[settings.width]?.class ?? WIDTHS.page.class, ...bodyClasses(settings)]
}
