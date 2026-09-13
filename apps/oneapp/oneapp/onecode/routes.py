"""Which path a tenant project claims, and what it may not claim.

`docs/UNIFICATION.md` §E9's fourth rail, and the whole of its argument is in
four words: **checked at save time**. A collision discovered when somebody
opens the page is a collision discovered by a customer, on a route that by then
has been linked to from somewhere; a collision discovered when somebody saves a
manifest is a sentence in a dialog.

Two kinds of collision, and they fail differently in production if they are not
caught here:

* **With ours.** `/one` is the SPA, `/api` is the framework, `/app` is the
  desk, `/assets` and `/files` and `/private` are static. A project that claims
  one of those does not shadow it — Frappe's own router wins — so the failure
  is a page that silently never loads, which is the worst kind to debug.
* **With another project's.** Here the project *does* win, whichever of the two
  the router reaches first, and which one that is depends on insertion order.
  One workspace, two projects, and a page that changes behaviour when somebody
  unrelated saves.

A claim is a prefix, not a path. `/shop` claims `/shop` and everything under
it, because a tenant app is an SPA with client-side routing and the shell has
to answer for every depth of it — which is what Frappe's `dynamic_route` is
for. That also means nesting is a collision: `/shop` and `/shop/admin` cannot
both be claimed, and the message says which one is in the way.
"""

import re

#: What this platform answers on, and will not hand over. `one` is the product
#: and the other five are the framework's; `dav` is ours, and it is in this
#: list rather than the next one because a mounted drive that stopped resolving
#: would look like a network fault for a week.
RESERVED = (
	"one", "api", "app", "assets", "files", "private", "dav",
	# Frappe's own website routes that a tenant would plausibly reach for.
	"login", "logout", "update-password", "signup", "me", "print", "method",
	# Ours, and the reason it is written down: the marketplace and the
	# readiness page are both pages a customer lands on from outside.
	"add", "ready", "billing",
)

#: A claim is lowercase letters, digits and hyphens, in segments. Deliberately
#: narrower than a URL allows: a route with an encoded character in it is a
#: route somebody will report as broken from one browser and not another.
SEGMENT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: How deep a claim may go. Three is already more than a claim needs — the
#: project routes below its own prefix — and a fifty-segment claim is either a
#: mistake or an attempt to be un-typeable in an error message.
MAX_SEGMENTS = 3


class Collision(ValueError):
	"""A route that cannot be claimed, with the reason a person reads."""


def normalise(route: str) -> str:
	"""`"/Shop/"` → `"shop"`. The stored form has no slashes on either end.

	Stored without them because every comparison below is between segments,
	and a trailing slash is the difference between two rows that mean the same
	claim — which is how a uniqueness check stops being one.
	"""
	return (route or "").strip().strip("/").lower()


def segments(route: str) -> list[str]:
	text = normalise(route)
	return text.split("/") if text else []


def validate(route: str) -> str:
	"""Refuse a claim nothing should be able to make. Answers the stored form."""
	parts = segments(route)
	if not parts:
		raise Collision("A project needs a route to be reached at.")
	if len(parts) > MAX_SEGMENTS:
		raise Collision(
			f"A route may be at most {MAX_SEGMENTS} segments deep; "
			f"“/{'/'.join(parts)}” is {len(parts)}."
		)
	for part in parts:
		if not SEGMENT.match(part):
			raise Collision(
				f"“{part}” is not a route segment. Use lowercase letters, "
				"digits and hyphens."
			)
	if parts[0] in RESERVED:
		raise Collision(
			f"“/{parts[0]}” belongs to the platform and cannot be claimed. "
			"Pick another first segment."
		)
	return "/".join(parts)


def under(claim: str, other: str) -> bool:
	"""Whether one claim is the same as, or inside, another.

	Prefix on *segments* rather than on the string, which is the difference
	between `/shop` containing `/shop/admin` — it does — and `/shop` containing
	`/shopping`, which it does not and which a `startswith` would say it did.
	"""
	one, two = segments(claim), segments(other)
	short, long = (one, two) if len(one) <= len(two) else (two, one)
	return long[: len(short)] == short


def check(route: str, taken: dict) -> str:
	"""Validate a claim against every claim already made.

	`taken` is `{route: project}` — the whole registry, handed in rather than
	read, so this stays a function over data and the one caller that knows
	where projects live is the one that reads them.
	"""
	claim = validate(route)
	for existing, project in sorted(taken.items()):
		if under(claim, existing):
			raise Collision(
				f"“/{claim}” collides with “/{normalise(existing)}”, which "
				f"{project} already claims."
			)
	return claim
