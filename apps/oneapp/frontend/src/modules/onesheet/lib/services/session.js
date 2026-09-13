/**
 * Who is signed in, for the workbook's avatar and its read-only gate.
 *
 * Ours, and it replaces something vendored. Upstream's `utils/session.js` used
 * to read `window.frappe.session` with a cookie fallback, and then moved that
 * question into the suite's own session store — which we do not have, and
 * should not: this product already answers it, once, in
 * `onespace/lib/shell/session.js`, and every other screen reads it there. A
 * workbook holding a second opinion about who you are is the drift worth not
 * having, and it was already halfway there: the vendored helper read a cookie
 * because `window.frappe` is the desk's global and this SPA is not the desk.
 *
 * Two sources, because the two callers ask at different moments. `sessionUser`
 * is on the boot payload and is there before the app mounts, which is what the
 * read-only gate needs — a grid that lets you type for a second and then stops
 * is worse than one that never did. The full name and the picture come off the
 * session resource and arrive a beat later, which is fine for an avatar.
 *
 * A stranger through `/one/link/<secret>` has neither, and answers empty. That
 * is the same "no" the gate wants and the same "no" the avatar wants.
 */

import { sessionUser } from '@/shared/lib/runtime/boot'
import { session } from '@/modules/onespace/lib/shell/session'

const GUEST = { user: '', fullName: '', image: '' }

export function getSessionUser() {
  if (!sessionUser || sessionUser === 'Guest') return GUEST
  const who = session.user || {}
  return {
    user: sessionUser,
    fullName: who.full_name || '',
    image: who.user_image || '',
  }
}
