"""One box over every space — what somebody types when they know the name.

The gap this closes is the one `docs/FRAPPE.md` named first: a person who knows
a customer's name and not which space it lives in had nowhere to type it, and
every space was searched by opening it.

**Not Frappe's global search**, and that was a measurement rather than a
preference. `__global_search` on the dev site holds 1,348 rows, of which 1,022
are `DocType`, 223 are `Report` and 55 are `Module Def` — it is the desk's own
metadata, and the business records a person actually looks for are barely in it.
Two things would still be wrong if it were full. It is a MySQL full-text index
queried with `MATCH … AGAINST` in natural-language mode, so it matches whole
words: typing `Meri` does not find `Meridian`, which is fatal for a box people
type four characters into. And a hit is a doctype and an id with no idea which
*screen* shows it — and a record nobody can open is not a search result here,
because `_refuse_ungranted` means a record is only ever reachable through a
screen that grants it.

**So the screens are what is searched.** For each screen this reader could open,
one `like` over the fields that screen lists, and a hit comes back already
knowing where to open it. That is the thing we have and Frappe does not: the
manifest already says which space and which screen a doctype belongs to.

Measured before it was written, because a fan-out over a hundred-odd tables is
the kind of design that sounds slow: one `get_list` with a `like` is about half
a millisecond, and the whole fan-out across all 146 doctypes the shipped
manifests name is **68 ms** for a real query. It is the pathological query —
two characters that match everything — that costs, and that is bounded by
`MOST` per screen and `TOTAL` overall rather than by the number of tables.

Three rules the fan-out inherits rather than re-decides, and all three are the
list's own:

  * **A hit is a row that screen would list.** The screen's declared filters
    apply, `@me` resolved the same way `mine.py` resolves it everywhere else,
    so a search cannot become a way around a narrowing — "my leave" stays mine.
  * **Only fields the screen shows are searched.** `filters.py` says why:
    watching which rows come back is a way of reading a column you were never
    given.
  * **`get_list`, so permissions are Frappe's own.** Nothing here passes
    `ignore_permissions`, and the targets come from `navigable`, which is
    already narrowed to the seat this person holds.

What is deliberately not here: the *other* half of a command palette. Going to
a screen needs no server at all — `api.session` already hands the browser every
space with its screens — and doing anything is `spaceview/actions.py`, which
already knows what a record offers. This module answers one question.
"""

import frappe
from frappe.utils import strip_html_tags

from oneapp.onespace import fieldtypes, mine
from oneapp.onespace.spaceview.filters import (
	MAX_SEARCH_COLUMNS,
	NEVER_SEARCHED,
	_search_text,
)

#: Rows taken from any one screen. A palette is a list somebody reads, so the
#: interesting answer is "which screens have this" rather than "here are forty
#: invoices" — and a screen that floods the answer is a screen that hides the
#: other nine.
MOST = 5

#: And in the whole answer, however many screens matched.
TOTAL = 40

#: Nothing is searched for less than this. Not a performance guard — `zz` costs
#: 490 ms because it matches everything, which is the shape of the cost — but a
#: product one: one letter matches half the workspace and answers nothing.
SHORTEST = 2

#: Screens looked at in one answer. A ceiling rather than a target: the shipped
#: manifests name 146 doctypes between them and a reader holds a fraction of
#: that, so this only ever bites on a workspace with every space enabled and
#: somebody holding every seat in all of them.
SCREENS = 200

#: Where a match landed, best first. A palette is read top-down and the id
#: somebody pasted has to be the first line, not the eleventh.
#:
#: `ELSEWHERE` is the one that is not about the title, and it is the difference
#: between a useful list and a list in arrival order. A row can match on any
#: column the screen shows, so a ledger entry named `09b526cc60` comes back for
#: `merid` because the account it is *against* says so — and with only four
#: ranks it tied with every genuine name match and won on sort order. A hit
#: whose own name does not contain what was typed is a hit somebody cannot see
#: the reason for, so it goes under all of them.
EXACT, STARTS, WORD, ANYWHERE, ELSEWHERE = 0, 1, 2, 3, 4


def _fields(doctype: str, listed: str) -> list[str]:
	"""The fields of one screen that a `like` can ask about.

	`name` first and always — the id is what people paste, and a screen whose
	columns are eleven text fields would otherwise spend the whole budget before
	reaching it.

	The rest are the screen's own columns, filtered exactly as the in-screen
	search box filters them. Same constants, imported rather than restated: a
	field nobody may search on one screen is not searchable from the palette
	either, and two copies of that list is one copy that goes stale.
	"""
	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		# A screen naming a doctype this site has not installed. The manifest
		# guards catch that; here it is one screen that answers nothing rather
		# than a palette that answers nothing.
		return []

	reach = ["name"]
	for fieldname in (listed or "").split(","):
		fieldname = fieldname.strip()
		if not fieldname or fieldname in reach:
			continue
		field = meta.get_field(fieldname)
		if not field or field.fieldtype in NEVER_SEARCHED:
			continue
		if "like" not in fieldtypes.operators_for(field.fieldtype):
			continue
		reach.append(fieldname)
		if len(reach) >= MAX_SEARCH_COLUMNS:
			break
	return reach


def _title_field(doctype: str, listed: list[str]) -> str:
	"""What to show as the hit's name.

	The doctype's own title field where it has one and the screen lists it —
	a hit reading `HR-EMP-00013` when the screen would have said `Bashir Haddad`
	is a result somebody has to open to identify.
	"""
	try:
		title = frappe.get_meta(doctype).title_field
	except Exception:
		return ""
	return title if title and title in listed else ""


def targets() -> list[dict]:
	"""Every screen this reader could open, as something to search.

	Deduplicated by doctype **within** a space and not across them, which is the
	honest answer to a doctype two spaces both list: a Sales Invoice really is
	reachable in OneBook and in RUA, they are different screens with different
	filters, and collapsing them would silently pick one. The same *record*
	turning up twice is handled where the results are ranked, not here.

	In manifest order, so the first screen a space declares over a doctype is
	the one its hits open in — which is the general list rather than a twin
	narrowed to one status.
	"""
	from oneapp.onespace import sync
	from oneapp.onespace.spaceview import navigable, visible

	found, seen = [], set()
	for space in visible(sync.state().get("spaces") or []):
		code = space.get("space_code") or ""
		for screen in navigable(space):
			doctype = (screen.get("document_type") or "").strip()
			if not doctype or (code, doctype) in seen:
				continue
			seen.add((code, doctype))
			found.append({
				"doctype": doctype,
				"space": code,
				"space_label": space.get("space_label") or code,
				"brand": space.get("brand") or "",
				"screen": screen.get("screen") or "",
				"label": screen.get("singular") or screen.get("label") or doctype,
				"icon": screen.get("icon") or "",
				"fields": screen.get("fields") or "",
				"filters": screen.get("filters") or "",
			})
			if len(found) >= SCREENS:
				return found
	return found


def _narrowing(target: dict) -> list:
	"""The screen's own filters, as `get_list` takes them.

	Through `mine.resolve`, so `@me` means the reader here exactly as it does
	when the screen itself is opened. A screen whose filters will not parse is
	searched unnarrowed rather than skipped — the permission check underneath
	is what keeps that safe, and the alternative is a screen that silently
	stops being findable.
	"""
	raw = target.get("filters")
	if not raw:
		return []
	try:
		declared = frappe.parse_json(raw) if isinstance(raw, str) else raw
	except Exception:
		return []
	if not isinstance(declared, dict):
		return []
	resolved = mine.resolve(declared)
	return [[fieldname, "=", value] if not isinstance(value, (list, tuple))
	        else [fieldname, value[0], value[1]]
	        for fieldname, value in resolved.items()]


def _where(text: str, title: str) -> int:
	"""How well one hit matches — `EXACT` down to `ELSEWHERE`."""
	low = (title or "").lower()
	if low == text:
		return EXACT
	if low.startswith(text):
		return STARTS
	if f" {text}" in f" {low}":
		return WORD
	return ANYWHERE if text in low else ELSEWHERE


def _hits(target: dict, text: str) -> list[dict]:
	"""One screen's answer, or nothing."""
	listed = _fields(target["doctype"], target["fields"])
	if not listed:
		return []

	title = _title_field(target["doctype"], listed)
	wanted = ["name", title] if title else ["name"]

	try:
		rows = frappe.get_list(
			target["doctype"],
			filters=_narrowing(target),
			or_filters=[[one, "like", f"%{text}%"] for one in listed],
			fields=wanted,
			order_by="modified desc",
			limit_page_length=MOST,
		)
	except frappe.PermissionError:
		# A screen whose grant and whose doctype permissions disagree. Absent
		# from the answer, which is what `navigable` would have done had it
		# known — never an error, because one bad screen must not take the
		# palette down with it.
		return []
	except Exception:
		frappe.clear_messages()
		return []

	found = []
	for seat, row in enumerate(rows):
		# Stripped, because a title field is not always plain text: OneTask's
		# subject is rich text, and a palette line reading
		# `<p>Chase the Halloway invoice</p>` is markup somebody has to read
		# past.
		shown = strip_html_tags(str(row.get(title) or row["name"])) if title else str(row["name"])
		shown = " ".join(shown.split()) or str(row["name"])
		found.append({
			"doctype": target["doctype"],
			"name": row["name"],
			"title": shown,
			# The id beside the title, and only where it is not the title
			# already — `TASK-0007 · TASK-0007` is a line that says one thing
			# twice.
			"id": row["name"] if shown != row["name"] else "",
			"space": target["space"],
			"space_label": target["space_label"],
			"brand": target["brand"],
			"screen": target["screen"],
			"label": target["label"],
			"icon": target["icon"],
			"rank": min(_where(text, shown), _where(text, row["name"])),
			# Where this hit sat in its own screen's answer. Read by the sort
			# below, which takes every screen's best hit before anybody's
			# second — a palette wants breadth before depth, and without it
			# one screen with five equally weak matches owns the visible list.
			"seat": seat,
		})
	return found


@frappe.whitelist(methods=["GET"])
def look(query: str = "", space: str = "") -> dict:
	"""What this person can find, from anywhere, for what they typed.

	`space` is where they were standing. It does not narrow anything — the
	whole point is that it does not — but it breaks the tie when one record is
	reachable from two spaces, and it lifts its own space's hits above equally
	good ones elsewhere. Somebody searching from inside OneBook means the
	invoice in OneBook.
	"""
	text = _search_text(query).strip().lower()
	if len(text) < SHORTEST:
		return {"query": text, "results": [], "looked": 0}

	found, looked = [], 0
	for target in targets():
		looked += 1
		found.extend(_hits(target, text))
		if len(found) >= TOTAL * 2:
			# Enough to rank well without walking the rest of the workspace.
			# Twice the ceiling rather than the ceiling, so the sort below is
			# still choosing between hits rather than reporting arrival order.
			break

	# One record, one line. Two spaces listing the same doctype each found it;
	# the one the reader is standing in wins, then manifest order.
	best: dict[tuple, dict] = {}
	for hit in found:
		key = (hit["doctype"], hit["name"])
		there = best.get(key)
		if there is None or (hit["space"] == space and there["space"] != space):
			best[key] = hit

	results = sorted(
		best.values(),
		key=lambda hit: (hit["rank"], hit["seat"],
		                 0 if hit["space"] == space else 1, hit["title"].lower()),
	)
	return {"query": text, "results": results[:TOTAL], "looked": looked}
