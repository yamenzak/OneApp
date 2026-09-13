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

/**
 * The five controls frappe-ui does not ship a menu item for.
 *
 * Derived from frappe/suite's Writer (AGPL-3.0, Copyright (c) Frappe
 * Technologies Pvt. Ltd. and contributors), `apps/writer/components/
 * core-editor/menu-buttons.js`, which writes the same five as plain objects
 * against the same `{label, icon, action, isActive, isAvailable}` shape
 * `frappe-ui/editor`'s own `command()` produces. Taken rather than invented
 * because there is nothing here to improve on: each is one tiptap command.
 *
 * **Every extension behind these was already loaded.** `RichTextKit` brings
 * Underline and, unless asked not to, TaskList and TaskItem — so a person
 * could already press ⌘U, and could make a checklist from the slash menu, and
 * the toolbar said neither existed. That is the whole of this change: the
 * capability was there and the chrome did not admit it.
 *
 * `isAvailable` rather than `isDisabled` where the command may not exist: a
 * control for an extension this editor was not built with should not be drawn
 * at all, which is also what keeps this list honest as the kit changes.
 */

const Underline = {
  label: __('Underline'),
  icon: 'lucide-underline',
  action: (editor) => editor.chain().focus().toggleUnderline().run(),
  isActive: (editor) => editor.isActive('underline'),
  isAvailable: (editor) => !!editor.can().toggleUnderline?.(),
}

/**
 * Formatting off, in one press.
 *
 * `unsetAllMarks` takes the bold and the colour; `clearNodes` takes the
 * heading, the quote and the list. Both, because a person who has pasted a
 * paragraph out of a browser means all of it — and the commonest thing anybody
 * does to pasted text is try to make it stop looking like where it came from.
 */
const ClearFormatting = {
  label: __('Clear formatting'),
  icon: 'lucide-remove-formatting',
  action: (editor) => editor.chain().focus().unsetAllMarks().clearNodes().run(),
}

const TaskList = {
  label: __('Checklist'),
  icon: 'lucide-list-checks',
  action: (editor) => editor.chain().focus().toggleTaskList().run(),
  isActive: (editor) => editor.isActive('taskList'),
  isAvailable: (editor) => typeof editor.commands.toggleTaskList === 'function',
}

/**
 * Nesting a list item, and un-nesting it.
 *
 * Tab and shift-tab already do both, and a great many people do not know that.
 * A capability reachable only by a shortcut nobody was told about is one the
 * product does not have.
 *
 * `isDisabled` where frappe/suite has `isAvailable`, and this is the one place
 * worth differing from them: a caret outside a list makes both commands
 * impossible, so under `isAvailable` the two buttons vanish and every control
 * to their right slides left — the toolbar rearranges itself as you move
 * through your own document. Drawn and greyed says the same thing and says it
 * in a fixed place. `isAvailable` stays where it belongs above, for the
 * commands that may genuinely not exist in this build.
 */
const Indent = {
  label: __('Indent'),
  icon: 'lucide-indent-increase',
  action: (editor) => editor.chain().focus().sinkListItem('listItem').run(),
  isDisabled: (editor) => !editor.can().sinkListItem('listItem'),
}

const Dedent = {
  label: __('Outdent'),
  icon: 'lucide-indent-decrease',
  action: (editor) => editor.chain().focus().liftListItem('listItem').run(),
  isDisabled: (editor) => !editor.can().liftListItem('listItem'),
}

export const documentToolbar = [
  Undo,
  Redo,
  Separator,
  HeadingGroup,
  Separator,
  Bold,
  Italic,
  Underline,
  Strike,
  InlineCode,
  FontColor,
  FontHighlight,
  ClearFormatting,
  Separator,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Separator,
  BulletList,
  OrderedList,
  TaskList,
  Blockquote,
  Dedent,
  Indent,
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
