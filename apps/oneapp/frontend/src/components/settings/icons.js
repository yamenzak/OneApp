/**
 * The icons the settings dialog's tabs draw.
 *
 * These literals are what make the CSS exist. frappe-ui renders `lucide-*`
 * names as Tailwind utility classes and the JIT only emits a class it can find
 * as a literal string in the source it scans — which is this directory, not
 * `oneapp_core/tabs.py`. A tab's icon is declared in Python now, where it
 * belongs with the audience that decides who sees the tab, so without this list
 * every one of them would render as an empty box.
 *
 * It is the same rule and the same fix as `lib/shell/icons.js`: never build an
 * icon class by interpolation, and keep a known set written out.
 *
 * `tests/test_settings_tabs.py` reads both ends and fails if a tab names an
 * icon that is not here — which is the only way to notice, because a missing
 * one is a blank space rather than an error.
 */
export const TAB_ICONS = [
  // You
  'lucide-circle-user',
  'lucide-lock',
  'lucide-bell-dot',
  'lucide-sun-moon',
  'lucide-at-sign',
  // Workspace
  'lucide-palette',
  'lucide-key-round',
  'lucide-globe',
  'lucide-book-open',
  'lucide-printer',
  'lucide-file-type',
  'lucide-hash',
  'lucide-mail',
  'lucide-file-text',
  'lucide-bell',
  'lucide-sparkles',
  'lucide-hard-drive',
  'lucide-users',
  'lucide-import',
  // The control plane adds its own groups through
  // `onespace_settings_groups`; these are the ones it names.
  'lucide-cloud',
  'lucide-credit-card',
  'lucide-server',
]
