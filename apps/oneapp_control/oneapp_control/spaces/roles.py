"""The four seats every space has.

A space used to invent its own jobs — a rep and a sales manager, an employee
and a people officer and payroll, a viewer and a planner and a feed manager —
and every one of them was a fresh decision about what a word meant. Twelve
words across five spaces, no two of which lined up, and a customer with three
spaces had to learn all twelve.

There are four seats and every space has exactly these four:

* **User** — does the work. The records this space is *for*, and nothing that
  decides their shape.
* **Manager** — runs the space. Everything the User reaches, plus the tables
  the work is measured by.
* **Admin** — owns the space. Everything the Manager reaches, plus its
  settings, its confidential lanes and anything destructive.
* **Audit** — reads it. Every doctype any other seat can reach, at Read, and
  writes nothing anywhere.

The first three are a ladder, so a manifest names **the lowest seat that may
do a thing** and the seats above inherit it. That is why nearly every grant in
this repository stayed exactly as it was written: an unroled row already meant
"anybody in this space", which is the User rung, and a row naming the manager
already meant "this seat and up".

Audit is not on the ladder. It is the same set of doctypes at Read, derived
rather than declared, so a space cannot ship an auditor who can write and
cannot forget to let one look at something.

A *key* is what a manifest and a membership store. A *Frappe role* is what the
tenant site holds, and it is `<prefix>-<Label>`: `CRM-User`, `HR-Manager`,
`Project-Audit`. The prefix is the space's `role_name`; the four names are
derived from it, so there is no list of role names anywhere to keep in step.
"""

USER = "user"
MANAGER = "manager"
AUDIT = "audit"
ADMIN = "admin"

LABELS = {USER: "User", MANAGER: "Manager", AUDIT: "Audit", ADMIN: "Admin"}

# Who inherits whom. A grant at `user` reaches manager and admin as well; one
# at `manager` reaches admin; one at `admin` stops there. Audit is absent
# deliberately — it is derived in `permission_manifest`, at Read.
ABOVE = {
	USER: (USER, MANAGER, ADMIN),
	MANAGER: (MANAGER, ADMIN),
	ADMIN: (ADMIN,),
	AUDIT: (AUDIT,),
}

ROLES = [
	{
		"role_key": USER,
		"label": LABELS[USER],
		"is_default": 1,
		"description": "Do the work this space is for. Reads the reference "
		               "tables behind it and changes none of them.",
	},
	{
		"role_key": MANAGER,
		"label": LABELS[MANAGER],
		"description": "Everything a User does, plus the tables the work is "
		               "measured by — the stages, the types, the reasons.",
	},
	{
		"role_key": AUDIT,
		"label": LABELS[AUDIT],
		"description": "Read every record in this space and write nothing. "
		               "The seat for an auditor, a board member or a lawyer.",
	},
	{
		"role_key": ADMIN,
		"label": LABELS[ADMIN],
		"description": "Owns the space: its settings, its confidential lanes "
		               "and anything that cannot be undone.",
	},
]

KEYS = tuple(row["role_key"] for row in ROLES)


def frappe_role(prefix: str, key: str) -> str:
	"""`CRM` and `manager` become `CRM-Manager`."""
	prefix = (prefix or "").strip()
	if not prefix or key not in LABELS:
		return ""
	return f"{prefix}-{LABELS[key]}"


def frappe_roles(prefix: str) -> list[str]:
	"""Every Frappe role one space becomes, in ladder order."""
	return [name for name in (frappe_role(prefix, key) for key in KEYS) if name]
