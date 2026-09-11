"""Frappe Cloud's own facts, as doctypes with no table.

Every fact about a site, a server or a bench group already exists in press. We
used to copy the ones we needed onto rows of our own — `Shard.press_server`,
`Shard.press_version`, `Shard.site_apps` — and a copy of somebody else's truth
has exactly one behaviour: it drifts. A bench upgraded in the Frappe Cloud
dashboard left our `press_version` saying what it used to be, and nothing
anywhere could tell.

So these are **virtual doctypes**: no table, no mirror, no migration. The
controller fetches from press on read and the framework does the rest —
permissions, list views, filters, the record engine, saved views. A screen
cannot tell one from an ordinary doctype, which is the whole reason the console
stayed a Frappe app.

Two rules follow from having no table, and both are load-bearing:

**Nothing here is ever written.** The permissions are read-only and the
controllers refuse `db_insert`, `db_update` and `delete` outright. Changing a
site is `press/client.py` — an operation with a job behind it — not a form save
that silently means something different from what it looks like.

**Nothing here can be joined or aggregated in SQL.** A list is an API call. So
anything we filter across the fleet on a hot path — which shard has headroom,
above all — stays a real column on a real table. That boundary is the whole
design: press owns what press knows, we own what we decide.
"""

import frappe
from frappe import _

from oneapp_control.press.client import PressError, get_client

#: How long a listing is reused. Long enough that a screen drawing a list, a
#: count and a sidebar does not make three round trips to press; short enough
#: that an operator who just changed something in the Frappe Cloud dashboard
#: sees it by the time they have switched tabs.
TTL = 60

#: What a page of a virtual list holds when nobody says. Frappe's own default
#: for a list view, so the console pages the way every other screen does.
PAGE = 20


def _cached(key: str, load):
	"""One press call per minute per key, however many readers there are."""
	full = f"oneapp_press:{key}"
	try:
		found = frappe.cache().get_value(full)
	except Exception:
		found = None

	if found is not None:
		return found

	try:
		found = load()
	except PressError:
		# A console screen that cannot reach press should say "nothing" and let
		# the operator read the error in the log, rather than 500 on a list
		# view. Not cached: the next request tries again.
		frappe.log_error(
			title=f"Press is not answering for {key}", message=frappe.get_traceback()
		)
		return []

	try:
		frappe.cache().set_value(full, found, expires_in_sec=TTL)
	except Exception:
		pass
	return found


def forget():
	"""Drop every cached listing. Called after anything that changes press."""
	keys = ["sites", "servers", "groups"]
	keys += [f"apps:{row.get('name')}" for row in (groups() or []) if row.get("name")]
	for key in keys:
		try:
			frappe.cache().delete_value(f"oneapp_press:{key}")
		except Exception:
			pass


# --------------------------------------------------------------------------- #
# The three listings
# --------------------------------------------------------------------------- #

def sites() -> list[dict]:
	return _cached("sites", lambda: get_client().sites())


def servers() -> list[dict]:
	return _cached("servers", lambda: get_client().servers())


def groups() -> list[dict]:
	return _cached("groups", lambda: get_client().release_groups())


def group_of(name: str) -> dict:
	"""One bench group's row, or an empty one."""
	return next((row for row in groups() if row.get("name") == name), {})


def site_plans() -> list[dict]:
	"""The plans press offers, cached with the rest.

	Read on every shard save to fill a default, so it must not be a round trip
	each time — and the list changes when Frappe Cloud changes its pricing,
	not when somebody opens a form.
	"""
	return _cached("site_plans", lambda: get_client().site_plans()) or []


def regions_of(name: str) -> list[dict]:
	"""Clusters a bench group can deploy into, cached like the rest.

	The pivot for a shard: pick a bench group and press already knows which
	machine, which cluster and therefore which region. Asking somebody to copy
	all three off another screen is asking them to get one wrong.
	"""
	return _cached(f"regions:{name}", lambda: get_client().group_regions(name)) or []


def servers_of(name: str) -> list[dict]:
	"""The servers a bench group runs on.

	`bench.all` names the group's server directly on most accounts; where it
	does not, every server in the group's clusters is a candidate and one
	candidate is an answer.
	"""
	group = group_of(name)
	direct = group.get("server") or group.get("server_name")
	if direct:
		return [row for row in servers() if row.get("name") == direct] or [{"name": direct}]

	clusters = {
		row.get("name") or row.get("cluster")
		for row in regions_of(name)
		if row.get("name") or row.get("cluster")
	}
	if not clusters:
		return []
	return [row for row in servers() if row.get("cluster") in clusters]


def version_of(name: str) -> str:
	"""Which Frappe version a bench group builds.

	Asked here rather than stored on the Shard. It used to be a required field
	somebody typed off another screen, checked against press on save and never
	again — so a bench upgraded afterwards left us telling press the version it
	used to be, and press answers a version mismatch by falling back to its
	public marketplace path and failing with an error about that instead.
	"""
	return group_of(name).get("version") or ""


def apps_of(name: str) -> list[str]:
	"""Every app on a bench group, in press's order.

	Cached per group: a screen asking what a workspace could install asks this,
	and the answer changes when somebody deploys rather than when somebody
	looks.
	"""
	rows = _cached(
		f"apps:{name}", lambda: get_client().group_apps(name)
	)
	found = []
	for app in rows or []:
		said = str(app.get("app") or app.get("name") or "").strip() if isinstance(app, dict) else str(app)
		if said and said not in found:
			found.append(said)
	return found


def tenants_by_site() -> dict[str, str]:
	"""Which workspace each press site belongs to, if any.

	The join that makes an orphan visible. Read as one query rather than per
	row: a fleet listing is one press call and one of these, whatever its
	length.
	"""
	return {
		row["press_site"]: row["name"]
		for row in frappe.get_all(
			"Tenant", filters={"press_site": ("is", "set")},
			fields=["name", "press_site"], limit_page_length=0,
		)
		if row.get("press_site")
	}


# --------------------------------------------------------------------------- #
# Standing in for the database
#
# `frappe.get_list` hands a virtual controller everything it parsed off the
# request — filters, fields, sort, page — and expects rows back. These four do
# that against a list of dicts, once, so three controllers are three field maps
# and no logic.
# --------------------------------------------------------------------------- #

def _values(row: dict, field: str):
	return row.get(field)


def matches(row: dict, condition) -> bool:
	"""One filter against one row, in Frappe's own operator vocabulary.

	Deliberately short. A virtual doctype is read by an operator narrowing a
	list of a few hundred rows, not by a report engine — and an operator
	vocabulary that quietly ignores an operator it does not know would show the
	wrong rows rather than refusing.
	"""
	if isinstance(condition, (list, tuple)):
		# Frappe passes either [fieldname, operator, value] or, once it has
		# resolved a doctype, [doctype, fieldname, operator, value].
		parts = list(condition)
		if len(parts) == 4:
			parts = parts[1:]
		if len(parts) == 2:
			field, wanted = parts
			operator = "="
		else:
			field, operator, wanted = parts
	else:
		return True

	value = _values(row, field)
	operator = (operator or "=").lower()

	if operator in ("=", "=="):
		return str(value or "") == str(wanted or "")
	if operator in ("!=", "not ="):
		return str(value or "") != str(wanted or "")
	if operator == "like":
		return str(wanted or "").strip("%").lower() in str(value or "").lower()
	if operator == "not like":
		return str(wanted or "").strip("%").lower() not in str(value or "").lower()
	if operator == "in":
		return str(value or "") in [str(one) for one in (wanted or [])]
	if operator == "not in":
		return str(value or "") not in [str(one) for one in (wanted or [])]
	if operator == "is":
		return bool(value) if wanted == "set" else not value

	frappe.throw(_("{0} is not something this list can be filtered by.").format(operator))


def narrow(rows: list[dict], filters) -> list[dict]:
	if not filters:
		return rows
	if isinstance(filters, dict):
		filters = [[field, "=", value] for field, value in filters.items()]
	return [row for row in rows if all(matches(row, one) for one in filters)]


def page(rows: list[dict], kwargs) -> list[dict]:
	"""Sort and slice, the way `get_list` was asked to."""
	order = (kwargs.get("order_by") or "").split(",")[0].strip()
	if order:
		# `\`tabPress Site\`.status desc` — and the table name has a space in
		# it, so the direction comes off the end rather than the column off the
		# front. Splitting on the first space gave "`tabPress", which sorted by
		# a field nothing has and therefore not at all.
		descending = order.lower().endswith(" desc")
		column = order.rsplit(" ", 1)[0] if order.lower().endswith((" asc", " desc")) else order
		field = column.split(".")[-1].strip("` ")
		if rows and field in rows[0]:
			rows = sorted(
				rows, key=lambda row: (row.get(field) is None, str(row.get(field) or "")),
				reverse=descending,
			)

	start = int(kwargs.get("limit_start") or 0)
	length = int(kwargs.get("limit_page_length") or PAGE)
	return rows[start : start + length] if length else rows[start:]


def listing(rows: list[dict], kwargs) -> list[dict]:
	"""The whole of a virtual `get_list`: narrow, sort, slice."""
	return page(narrow(rows, kwargs.get("filters")), kwargs)


def counted(rows: list[dict], kwargs) -> int:
	return len(narrow(rows, kwargs.get("filters")))


def read_only(doctype: str):
	"""What every controller here does instead of writing.

	Said as a refusal rather than a silent no-op: a form that saves and changes
	nothing is worse than one that will not save, and the way to change a site
	is an operation with a job behind it.
	"""
	frappe.throw(
		_("{0} is Frappe Cloud's record, not ours. Change it there, or through "
		  "an action on the workspace.").format(_(doctype)),
		frappe.PermissionError,
	)
