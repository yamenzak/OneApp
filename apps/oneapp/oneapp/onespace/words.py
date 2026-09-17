"""The workspace's own word for a screen somebody else named.

`docs/ONECRM.md` stage 7. **Deal** and **Lead** are the house words of one
industry. They are the right default — a sales desk opening OneCRM should not
have to name anything — and they are the wrong answer for a charity with
donors, a clinic with referrals and a council with planning applications. The
same is true of Organisations in a workspace that sells to private people,
which is the checkpoint this exists for.

So a screen's label is a **default**, and a `OneSpace Word` row is what a
workspace calls it instead.

Three decisions.

**An overlay, not an edit.** The screens arrive from the control plane on every
sync and are rewritten wholesale, so a label typed into an `OneSpace Space
Screen` row would survive until the next fifteen minutes elapsed. A row of our
own outlives every sync and every release, and it is obvious afterwards what
was changed and what shipped.

**Applied in one place.** `sync.state()` builds the space list every other
surface reads — the rail, the switcher, the resolver, the breadcrumbs, the New
button, the assistant's own idea of where things are — so overlaying it there
is the difference between renaming a screen and renaming it in nine places that
must not disagree.

**The word is not the key.** `screen` stays what the address bar spells, so a
rename changes no url, no saved view, no bookmark and no declaration. This
renames what a person reads and nothing a machine reads.
"""

import frappe

WORD = "OneSpace Word"

#: The cache holds the whole map, because the alternative is a query per screen
#: on every request that draws a rail. Short, and cleared on write — a rename
#: somebody cannot see the result of is a rename they will do again.
CACHE_KEY = "onespace_words"
CACHE_TTL = 300


def spoken() -> dict:
	"""Every renamed screen, keyed `space_code/screen`."""
	cached = frappe.cache().get_value(CACHE_KEY)
	if cached is not None:
		return cached

	found = {}
	try:
		for row in frappe.get_all(WORD, fields=["space_code", "screen", "label",
		                                        "singular"]):
			code = (row.get("space_code") or "").strip()
			screen = (row.get("screen") or "").strip()
			label = (row.get("label") or "").strip()
			if not code or not screen or not label:
				continue
			found[f"{code}/{screen}"] = {
				"label": label,
				# Blank falls back to the label rather than to the shipped
				# singular: a workspace that renamed Deals to Donations and
				# left this empty means Donation, not Deal.
				"singular": (row.get("singular") or "").strip() or label,
			}
	except Exception:
		# A bench that has not migrated this doctype yet, or a reader with no
		# permission on it. A rail drawn in the shipped words is right; a rail
		# that will not draw is not.
		frappe.clear_last_message()
		found = {}

	frappe.cache().set_value(CACHE_KEY, found, expires_in_sec=CACHE_TTL)
	return found


def renamed(spaces: list) -> list:
	"""The same spaces, in the words this workspace uses.

	Copies rather than mutates: `state()` caches what it builds, and a list
	rewritten in place is a list some other caller already has a reference to.
	"""
	said = spoken()
	if not said:
		return spaces

	out = []
	for space in spaces:
		code = (space or {}).get("space_code") or ""
		screens = (space or {}).get("screens") or []
		if not any(f"{code}/{(one or {}).get('screen')}" in said for one in screens):
			out.append(space)
			continue
		out.append({**space, "screens": [_said(code, one, said) for one in screens]})
	return out


def _said(code: str, screen: dict, said: dict) -> dict:
	"""One screen, in the workspace's words where it has one."""
	word = said.get(f"{code}/{(screen or {}).get('screen')}")
	if not word:
		return screen
	return {**screen, "label": word["label"], "singular": word["singular"]}


def forget(doc=None, method=None) -> None:
	"""Drop the cached map. Hooked on write, so a rename shows on the next page.

	`sync`'s own cache goes too: it holds the space list this overlays, and a
	rename that waited five minutes for that one to expire would look like it
	had not been saved.
	"""
	frappe.cache().delete_value(CACHE_KEY)
	from oneapp.onespace import sync

	frappe.cache().delete_value(sync.CACHE_KEY)


#: The screen every space has for its own words, whether it asked or not.
#:
#: Appended here rather than declared in nine manifests, for the reason
#: `sync.configured` gives about the Configuration page: a space says what it
#: *is*, and every space gets the same machinery over whatever that turns out
#: to be. A manifest declaring it would be eight lines repeated and forgotten
#: in the ninth.
SCREEN = "words"


def worded(spaces: list) -> list:
	"""Give every space a page for the words it calls its screens by.

	`hide_in_nav`, because this is not a place to go and work: it is a tab on
	the Configuration page, which is where the rest of a space's own tables
	are. Filtered to this space, and its New dialog starts with the space code
	already in — a page narrowed by a filter whose New made a row the page
	would not then show is the thing `view_settings.create` was added for.

	Skipped where the space has nothing to rename, which is a space with no
	screens; and skipped whole on the control plane, an operator console rather
	than a workspace.
	"""
	from oneapp.onespace import one as ONE

	if ONE.CONTROL_APP in (frappe.get_installed_apps() or []):
		return spaces

	out = []
	for space in spaces:
		code = (space or {}).get("space_code") or ""
		screens = (space or {}).get("screens") or []
		if not code or not screens:
			out.append(space)
			continue
		if any((one or {}).get("screen") == SCREEN for one in screens):
			out.append(space)
			continue
		out.append({**space, "screens": [*screens, _page(code)]})
	return out


def _page(code: str) -> dict:
	"""The Words screen for one space."""
	return {
		"screen": SCREEN,
		"hide_in_nav": 1,
		"label": frappe._("Words"),
		"singular": frappe._("Word"),
		"icon": "lucide-tag",
		"document_type": WORD,
		"fields": "screen,label,singular",
		"order_by": "screen asc",
		"view_types": "list",
		"filters": frappe.as_json({"space_code": code}),
		"view_settings": frappe.as_json({"create": {"values": {"space_code": code}}}),
	}
