/**
 * The icons an app in the registry may use.
 *
 * These literals are what make the CSS exist. frappe-ui renders `lucide-*`
 * names as Tailwind utility classes, and the JIT only emits a class it can find
 * as a literal string — so an icon name that only ever exists in the database
 * renders as an empty box. The icons page gives two ways out: a known set
 * written as literals, or `~icons/lucide/*` imports for a genuinely open one. A
 * registry of apps we define is a known set.
 *
 * Never build an icon class by interpolation; the scanner cannot see it.
 *
 * Generated from scripts/app_icons.py, which also writes the doctype's Select
 * options, so the picker and the stored values cannot drift.
 */

export const APP_ICONS = [
  'lucide-layout-grid',
  'lucide-users',
  'lucide-user-round',
  'lucide-briefcase',
  'lucide-file-text',
  'lucide-receipt',
  'lucide-wallet',
  'lucide-shopping-cart',
  'lucide-package',
  'lucide-truck',
  'lucide-factory',
  'lucide-store',
  'lucide-calendar',
  'lucide-clock',
  'lucide-message-square',
  'lucide-mail',
  'lucide-phone',
  'lucide-chart-line',
  'lucide-chart-pie',
  'lucide-database',
  'lucide-book-open',
  'lucide-graduation-cap',
  'lucide-stethoscope',
  'lucide-wrench',
  'lucide-shield',
  'lucide-sparkles',
]

export const DEFAULT_APP_ICON = 'lucide-layout-grid'

/** A name we know renders — for anything stored before the set was narrowed. */
export function appIcon(name) {
  return APP_ICONS.includes(name) ? name : DEFAULT_APP_ICON
}
