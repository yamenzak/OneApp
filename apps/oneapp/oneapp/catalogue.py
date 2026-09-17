"""Everything this app is made of, and what kind of thing each one is.

`docs/CLEANUP.md` §1 says there are two kinds and only two — a **space** is a
department you enter, a **service** is something every department uses — and
stage 1 said so in the browser. This is the other half: the server's own
declaration, and the one place the question is answered.

It was answered in four places before, none of which agreed on the whole set.
`modules.txt` lists the eleven Frappe modules that own doctypes and says
nothing about the rest. `oneapp_control/spaces/*.py` knows the six spaces the
control plane ships and nothing about a service. `scripts/brand/marks.json` has
twenty-seven drawings and no idea which are real. `lib/shell/apps.js` had the
kinds, in the browser, where the server cannot read them.

So: one row per thing, three identities on it, and every one of them optional
except the id.

* **`id`** — the directory, the space code in the URL, the key a manifest names
  a mark by. Always present and never product-facing; `CLAUDE.md` is emphatic
  about this and four of them disagree with their product name on purpose.
* **`module`** — the Frappe module name, for the ten that own doctypes. `None`
  for a space over somebody else's schema (OnePeople is HRMS's, OneProject is
  ERPNext's) and for a service that lives inside another module's directory.
* **`mark`** — the drawing, where there is one. `onelegal` has none: it is a
  service nothing puts a tile on.

**A module that owns doctypes cannot move.** `frappe.get_module_path` resolves
a module to the *import path* `oneapp.<scrubbed name>`, so `OneCRM` is
`oneapp/onecrm/` and nesting it under a `spaces/` package would be inventing a
Frappe convention no other app uses. §4's tree is therefore a description of
what a directory *is*, which this file supplies, rather than where it sits.

Nothing is derived from a directory listing. A row here is a decision, and the
guards in `tests/test_catalogue.py` hold the directories, `modules.txt`, the
marks and the browser's catalogue to it.
"""

#: A department you enter. Owns a body of records, has a rail, is bought and
#: granted as a unit, and has the four seats in `spaces/roles.py`.
SPACE = "space"

#: Something every department uses. Opens *over* whatever you are doing rather
#: than being somewhere you go. Every member has it; it has no seats of its
#: own, because storage is storage.
SERVICE = "service"

#: The desk itself. One row, and it is the thing the other two stand in.
ENGINE = "engine"


def _one(id: str, kind: str, module: str | None = None,
         mark: str | None = "", built: bool = True) -> dict:
	# `mark` defaults to the id because that is the case for all but three of
	# them, and a default of `None` would have every row restating itself.
	return {"id": id, "kind": kind, "module": module,
	        "mark": id if mark == "" else mark, "built": built}


CATALOGUE = (
	# The desk. `one` is the mark; `OneSpace` is the module the engine lives
	# in. They are the same thing under two names, which is why this is the
	# one row where the id and the module look unrelated.
	_one("one", ENGINE, module="OneSpace"),

	# The services, in the order the dock and the board put them.
	_one("onemail", SERVICE, module="OneMail"),
	_one("onecalendar", SERVICE, module="OneCalendar"),
	_one("onestorage", SERVICE, module="OneStorage"),
	_one("onedoc", SERVICE, module="OneDoc"),
	_one("onesheet", SERVICE, module="OneSheet"),
	_one("onecode", SERVICE, module="OneCode"),
	_one("onetask", SERVICE, module="OneTask"),
	_one("oneai", SERVICE, module="OneAI"),
	# A service with no module of its own: OneHub is a page on the control
	# plane, which is exactly what a null module means.
	_one("onemarket", SERVICE, module=None),
	# And one with a module and no drawing. Agreements are something every
	# space writes and nowhere puts a tile — `docs/LEGAL.md`.
	_one("onelegal", SERVICE, module="OneLegal", mark=None),

	# The spaces. Two own doctypes of ours; the rest are spaces over somebody
	# else's schema, which is the shape `docs/ERP-SPACES.md` argues for.
	_one("onecrm", SPACE, module="OneCRM"),
	_one("onemobility", SPACE, module="OneMobility"),
	_one("onehr", SPACE, module=None),
	_one("oneproject", SPACE, module=None),
	_one("onebook", SPACE, module=None),
	_one("oneinventory", SPACE, module=None),
	# The operator console, which is a space and is not in the browser's
	# catalogue: it is a different product on a different host, and the one
	# row that leaves this workspace is already in the switcher's foot.
	# Built since `docs/CLEANUP.md` stage 8 — `oneapp_control/spaces/oneadmin.py`,
	# declared the same way as the five beside it and read by the same guards.
	_one("oneadmin", SPACE, module=None),

	# Drawn and not built. Each carries the kind it *will* be rather than a
	# kind meaning "not yet", because what a thing is does not depend on
	# whether it exists: a helpdesk is a department and a signature is
	# something every department needs.
	_one("onescratchpad", SERVICE, built=False),
	_one("oneforms", SERVICE, built=False),
	_one("oneslide", SERVICE, built=False),
	_one("onesignature", SERVICE, built=False),
	_one("onedb", SERVICE, built=False),
	_one("oneticket", SPACE, built=False),
	_one("onedisplay", SPACE, built=False),
	_one("onegovernance", SPACE, built=False),
	_one("onefit", SPACE, built=False),
	_one("onestudy", SPACE, built=False),
)

BY_ID = {row["id"]: row for row in CATALOGUE}


def kind_of(id: str) -> str | None:
	row = BY_ID.get(id)
	return row["kind"] if row else None


def of_kind(kind: str, built: bool | None = True) -> list[dict]:
	"""Every row of one kind. `built=None` for all of them, drawings included."""
	return [row for row in CATALOGUE
	        if row["kind"] == kind and (built is None or row["built"] == built)]


def modules() -> dict[str, str]:
	"""The Frappe modules this app carries, against the id that owns each.

	Read back against `modules.txt` by a guard: a module in one and not the
	other is a directory nobody declared or a declaration with no code.
	"""
	return {row["module"]: row["id"] for row in CATALOGUE if row["module"]}
