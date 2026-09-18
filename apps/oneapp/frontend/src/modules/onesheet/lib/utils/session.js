// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/suite (95c38bfdd975), frontend/src/apps/sheets/utils/session.js,
// which is AGPL-3.0. One is AGPL-3.0 too and this file stays that way
// — see lib/VENDORED.md before editing or moving it.

// Two-letter initials for the avatar, derived from a full name
// ("Asif Mulani" → "AM"); falls back to the first letter of the email, then
// "U" so the avatar never collapses into something empty.
//
// Identity itself comes from the shared suite session store (@/boot/session);
// this is only the presentation helper shared by the avatar, the collab
// presence pile, and the ShareDialog owner row.
export function userInitials(fullName, email) {
  const fn = (fullName || '').trim()
  if (fn) {
    const parts = fn.split(/\s+/)
    return ((parts[0][0] || '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
  }
  return (email ? email[0] : 'U').toUpperCase()
}
