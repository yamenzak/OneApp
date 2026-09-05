/**
 * Keyboard shortcuts for a screen, and the two rules that make them safe.
 *
 * A mail reader without them is a mail reader people leave: reading a morning's
 * post is the same three actions forty times, and reaching for the mouse each
 * time is the whole cost. Every client converged on the same letters — j, k, e,
 * u, s, c — because Gmail taught them, and a product that picks different ones
 * is asking people to learn something for nothing.
 *
 * The two rules:
 *
 * * **Never while somebody is typing.** A shortcut that fires inside a search
 *   box archives mail while you are looking for it. Anything focused that takes
 *   text — an input, a textarea, a contenteditable, and so a rich editor — is
 *   left alone, as is any key pressed with Ctrl or Meta held unless the
 *   shortcut asked for it.
 * * **Never over a dialog.** A dialog is a conversation with one thing, and the
 *   screen behind it is not listening. `document.querySelector('[role=dialog]')`
 *   is how that is known, because it is what every frappe-ui overlay renders.
 *
 * A binding is written the way it is pressed: `'e'`, `'shift+u'`, `'mod+z'`,
 * `'?'`. `mod` is Cmd on a Mac and Ctrl everywhere else, which is the one
 * difference worth carrying rather than picking a side.
 */
import { onBeforeUnmount, onMounted } from 'vue'

/** True on a Mac, where the modifier people press is Cmd. */
export const isMac =
  typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || '')

/** What to print in a shortcut list: `⌘Z` reads wrong on Windows. */
export const MOD = isMac ? '⌘' : 'Ctrl'

/** Whether the thing with focus is somewhere text goes. */
export function isTyping(target) {
  const node = target
  if (!node || !node.tagName) return false
  if (node.isContentEditable) return true
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(node.tagName)
}

/** The binding a key event matches, in the same spelling `bind` takes. */
export function pressed(event) {
  const key = event.key === ' ' ? 'space' : (event.key || '').toLowerCase()
  const mod = isMac ? event.metaKey : event.ctrlKey
  // Shift is only named when it changes which key it is — `shift+u` is a
  // different shortcut from `u`, but `?` is already shifted and naming it
  // `shift+?` would be describing the keyboard rather than the press.
  const shift = event.shiftKey && key.length === 1 && /[a-z]/.test(key)
  return `${mod ? 'mod+' : ''}${shift ? 'shift+' : ''}${key}`
}

/**
 * Bind a map of `{ 'e': fn }` for as long as the component is on screen.
 *
 * A handler that returns nothing gets the event's default prevented, because a
 * shortcut that also scrolls the page is a shortcut that half worked. One that
 * returns `false` says it did not handle this after all — which is how a key
 * can mean one thing when there is a selection and nothing when there is not.
 */
export function useShortcuts(map) {
  function onKey(event) {
    if (isTyping(event.target)) return
    if (document.querySelector('[role="dialog"]')) return

    const handler = map[pressed(event)]
    if (!handler) return
    if (handler(event) === false) return
    event.preventDefault()
  }

  onMounted(() => window.addEventListener('keydown', onKey))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
}
