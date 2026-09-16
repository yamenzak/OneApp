/**
 * Files you have open, as windows.
 *
 * A document and a sheet used to open in the Drive's pane — beside the list,
 * which was right while the Drive was a page and the pane was 45% of a laptop.
 * OneCloud is a window now, and a pane inside a 1040-pixel window is four
 * columns of a spreadsheet. So they open in windows of their own.
 *
 * **And this is the line the record preview's rule was really drawing.**
 * `docs/DESKTOP.md` stage 5 says a window holds something you consult or pick
 * from, never something you work in — and that was a conclusion about a
 * *record*, for three reasons that are all about what a record is: its Link
 * fields open more windows, its band submits a document somebody opened to
 * glance at, and a form you type into inside a frame that closes when you
 * click past it loses what was typed.
 *
 * A document has none of those. It has no links that peek, nothing that
 * submits, and it saves as you type — the editor is bound to a Y.Doc, so
 * there is no such thing as unsaved work in one. The rule stands where it was
 * made and this is not an exception to it: what a window must not hold is
 * *unsaved state and a submit*, and a record has both where an editor has
 * neither.
 *
 * One corner between them, the way record previews share one: they are the
 * same window to the person dragging it, and a box per file is a window that
 * opens somewhere new every time you look at a different sheet.
 */
import { computed, reactive } from 'vue'

import { close as closeWindow, open as openWindow } from '@/modules/onespace/lib/desk/windows'
import { editorFor } from '@/modules/onestorage/lib/files'

/** The family every file window's id starts with — `lib/desk/windows.js`. */
export const EDITOR = 'file:'

/** The one box they share. */
export const CORNER = 'file'

/**
 * Which app's colour a file's window wears, by the editor behind it.
 *
 * A branch rather than a map, and the reason is a guard rather than taste:
 * `editorFor` calls one of its four answers `text`, and a map keyed on it
 * reads as `text: 'onedoc'` to the i18n scan — which is looking for exactly
 * that shape, because `text="Save"` is how an untranslated label hides. The
 * scan is right to be blunt; this is the call site that should not have been
 * a map.
 *
 * Plain text is OneWriter's, not OneCode's: a `.txt` is something somebody
 * wrote, and the editor behind it only differs in what it can colour.
 */
export const brandFor = (editor) => {
  if (editor === 'sheet') return 'onesheet'
  if (editor === 'code') return 'onecode'
  return 'onedoc'
}

/**
 * What is open — `{ name, kind, label, editor }`, outermost first.
 *
 * Reactive and not derived from the URL, deliberately. `docs/DESKTOP.md`:
 * which windows are open is not an address, because a pasted link opens the
 * page and not somebody else's desk. A file you opened beside what you were
 * doing is exactly that kind of fact.
 */
const held = reactive([])

export const openFiles = computed(() => held)

/** Whether this one is already on the desk. */
const at = (name) => held.findIndex((one) => one.name === name)

/**
 * Open a file in a window, or raise the one it is already in.
 *
 * Returns whether it took it. A file with no editor of ours — a photograph, a
 * PDF, a video — is not a window: it is a thing you look at, and the pane
 * beside the list is the right shape for looking.
 */
export function openFile(file) {
  const editor = editorFor(file)
  if (!editor) return false

  const id = `${EDITOR}${file.name}`
  if (at(file.name) === -1) {
    held.push({
      name: file.name,
      kind: file.custom_kind || '',
      label: file.file_name || file.name,
      editor,
    })
  }
  openWindow(id, {
    label: file.file_name || file.name,
    brand: brandFor(editor),
    family: EDITOR,
  })
  return true
}

export function closeFile(name) {
  const found = at(name)
  if (found === -1) return
  held.splice(found, 1)
  closeWindow(`${EDITOR}${name}`)
}
