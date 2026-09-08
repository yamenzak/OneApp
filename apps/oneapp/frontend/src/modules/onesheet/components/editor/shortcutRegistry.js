/**
 * `useShortcut` — the API this editor was written against, over the one
 * frappe-ui ships now.
 *
 * Frappe Sheets registers shortcuts as `{ key: 's', ctrl: true, description,
 * group, handler }`. frappe-ui 1.0 replaced that with a combo string:
 * `{ combo: 'Mod+S', description, group, handler }`, where `Mod` is Cmd on a
 * Mac and Ctrl everywhere else — which is what the old `ctrl` flag meant, so
 * the translation is exact rather than approximate.
 *
 * Kept as an adapter rather than rewritten in place because the shortcut list
 * upstream is long, changes, and is the source of truth for the help dialog.
 * One function here is a smaller thing to re-sync than two hundred lines of
 * re-spelled registrations.
 */

import { useKeyboardShortcut } from 'frappe-ui'

// The keys whose combo name is not just the character. Everything punctuation-
// shaped is matched by `event.code` upstream so a shifted layout still
// resolves — `Mod+Shift+Digit1` fires on `!` as well as on `1`.
const NAMES = {
  ' ': 'Space',
  '+': 'Plus',
  '-': 'Minus',
  '=': 'Equal',
  '`': 'Backtick',
  '/': 'Slash',
  '\\': 'Backslash',
  ',': 'Comma',
  '.': 'Period',
  ';': 'Semicolon',
  "'": 'Quote',
  '[': 'BracketLeft',
  ']': 'BracketRight',
  0: 'Digit0',
  1: 'Digit1',
  2: 'Digit2',
  3: 'Digit3',
  4: 'Digit4',
  5: 'Digit5',
  6: 'Digit6',
  7: 'Digit7',
  8: 'Digit8',
  9: 'Digit9',
}

/** Nothing. Display-only entries exist so the help dialog lists them. */
const NOTHING = () => {}

export function useShortcut(shortcuts) {
  const list = Array.isArray(shortcuts) ? shortcuts : [shortcuts]
  const configs = []

  for (const entry of list) {
    const combo = comboOf(entry)
    if (!combo) continue
    configs.push({
      combo,
      description: entry.description,
      group: entry.group || 'General',
      // A display-only entry (grid navigation, handled by the canvas itself)
      // has no handler and must not swallow the key.
      preventDefault: entry.handler ? entry.preventDefault !== false : false,
      handler: entry.handler || NOTHING,
    })
  }

  if (configs.length) useKeyboardShortcut(configs)
}

function comboOf(entry) {
  const raw = String(entry?.key ?? '')
  if (!raw) return ''
  const key = NAMES[raw] ?? (raw.length === 1 ? raw.toUpperCase() : raw)
  // The order is the canonical spelling frappe-ui parses: Mod, Ctrl, Alt,
  // Shift, key. Anything else it rejects outright.
  return `${entry.ctrl ? 'Mod+' : ''}${entry.alt ? 'Alt+' : ''}${entry.shift ? 'Shift+' : ''}${key}`
}
