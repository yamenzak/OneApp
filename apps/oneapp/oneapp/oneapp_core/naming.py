"""Naming: what a record's id looks like before anybody types one.

Frappe answers this three ways and the difference matters, because only one of
them is a thing a customer should be editing:

* **`autoname`** on the doctype — `hash`, `field:title`, `format:{}-{}`, or a
  literal series like `EV.#####`. It is part of what the doctype *is*, it is
  set by whoever wrote the app, and it is not ours to change from a settings
  page: an app that names its records by hash and a workspace that decided
  otherwise is an app whose author will be very surprised.
* **`naming_series`** — a Select field on the document, whose options are the
  prefixes this workspace uses and whose value is the one it will use next.
  This is the customer-facing one: "our invoices start ACME-INV-" is a
  business decision, and Frappe stores it as a Property Setter on the field
  rather than as an edit to the doctype, which is exactly why it is safe to
  offer.
* **`Document Naming Rule`** — a prefix chosen by condition, for the doctype
  where one series is not enough.

So this module offers the second and reads the first. It is a gate and a
shape over `Document Naming Settings`, the same way `printing` is one over the
print stack — every write goes through Frappe's own methods, because the
counter, the Property Setter, the duplicate check across doctypes and the
Version log are four things that have to happen together and it already does
all four.

**What a workspace may reach.** Only the doctypes its own spaces granted, and
only those that have a `naming_series` field at all. The desk's own version of
this page offers every doctype on the site.
"""

import frappe
from frappe import _

from oneapp.oneapp_core import sync

# How many series one doctype may carry. Frappe bounds none; a Select with
# forty options is a control nobody reads to the end of, and a workspace that
# wants forty prefixes wants a naming rule.
SERIES = 10

# How long one prefix may be. `NamingSeries.validate` refuses the obviously
# broken ones; this refuses the ones that are merely unusable.
PREFIX = 40


def _granted() -> set[str]:
	"""Every doctype this workspace's screens show.

	The screens rather than every doctype on the site, which is what the desk's
	own naming page offers. A workspace that can rename `Error Log` has been
	handed the platform's own bookkeeping to break.
	"""
	return sync.granted_doctypes()


def _meta(doctype: str):
	try:
		return frappe.get_meta(doctype)
	except frappe.DoesNotExistError:
		return None


def _kind(doctype: str) -> str:
	"""How this doctype is named, in the two ways that have a counter.

	`series` — a `naming_series` field, whose options are prefixes a workspace
	may edit and whose value is the one a new record uses. This is the one
	ERPNext doctypes have and the one Frappe's own settings page is about.

	`autoname` — no such field, but the doctype's own `autoname` *is* a series:
	`EV.#####`, `ACC-JV-.YYYY.-`. The prefixes are not editable — they are part
	of what the doctype is, and changing one from a settings page would rename
	the scheme its author chose — but the **counter** is exactly as real, and a
	workspace that has just imported four years of history absolutely wants to
	move it. Frappe's own page reaches these too, through the same `Series`
	table; it simply never says which kind it is looking at.

	Anything else — `hash`, `field:title`, `prompt`, `format:` — has no counter
	and nothing here to show.
	"""
	meta = _meta(doctype)
	if not meta:
		return ""
	if meta.get_field("naming_series"):
		return "series"
	autoname = str(getattr(meta, "autoname", "") or "")
	if "#" in autoname and not autoname.lower().startswith(("hash", "field:", "prompt", "format:")):
		return "autoname"
	return ""


def _named(doctype: str) -> bool:
	"""Whether this doctype is named by anything with a counter under it."""
	return bool(_kind(doctype))


def doctypes() -> list[dict]:
	"""The doctypes a workspace may set a series for, with what they use now."""
	found = []
	for doctype in sorted(_granted()):
		if not _named(doctype):
			continue
		if not frappe.has_permission(doctype, "read"):
			# A doctype the space granted and this person's role does not
			# reach. Absent rather than refused: a settings page listing what
			# you cannot open is a settings page that lies about your access.
			continue
		found.append({
			"doctype": doctype,
			"label": _(doctype),
			# Whether the prefixes themselves may be edited, or only the
			# counter under them. A control that is drawn and a write that is
			# allowed have to read the same flag.
			"editable": _kind(doctype) == "series",
			"series": options(doctype),
		})
	return found


def options(doctype: str) -> list[dict]:
	"""The prefixes this doctype offers, and where each one has got to.

	The counter is read per prefix rather than per doctype because that is what
	it is: `Series` is keyed on the prefix, so two doctypes sharing one prefix
	share one counter — which is a thing people do on purpose and a thing
	nobody expects when they have not.
	"""
	from frappe.model.naming import NamingSeries

	meta = _meta(doctype)
	if not meta:
		return []

	field = meta.get_field("naming_series")
	if field:
		declared = [one.strip() for one in str(field.options or "").split("\n") if one.strip()]
		default = field.default or ""
	else:
		# The doctype's own `autoname`, which is one series and is the default
		# by definition — there is nothing else for a record to be named by.
		declared = [str(getattr(meta, "autoname", "") or "").strip()]
		declared = [one for one in declared if one]
		default = declared[0] if declared else ""

	found = []
	for prefix in declared:
		try:
			current = NamingSeries(prefix).get_current_value()
		except Exception:
			# A template whose prefix depends on a field cannot be resolved
			# without a document, and a settings page is not the place to
			# invent one. Shown without a counter rather than dropped.
			frappe.clear_last_message()
			current = None
		found.append({
			"prefix": prefix,
			"current": current,
			"default": prefix == default,
		})
	return found


def _reachable(doctype: str):
	"""The doctype, if this workspace may name it."""
	if doctype not in _granted() or not _named(doctype):
		frappe.throw(_("{0} is not named by a series here.").format(doctype))
	# The same rule the rest of the product uses: what you may change is a
	# subset of what you may read.
	if not frappe.has_permission(doctype, "write"):
		frappe.throw(_("You cannot change how {0} is named.").format(doctype),
		             frappe.PermissionError)


def set_options(doctype: str, series: list) -> list[dict]:
	"""Replace the prefixes this doctype offers.

	Through `Document Naming Settings`, which is where the four things that
	have to happen together already happen: the names are validated, the
	prefixes are checked against every *other* doctype on the site so two
	cannot share a counter by accident, the Property Setter is written on the
	field rather than on the doctype, and the doctype's cache is cleared.
	"""
	_reachable(doctype)
	if _kind(doctype) != "series":
		frappe.throw(
			_("{0} is named by its own scheme, which is part of the app rather "
			  "than a setting. Its counter can still be moved.").format(doctype)
		)

	wanted = [str(one or "").strip()[:PREFIX] for one in (series or [])]
	wanted = [one for one in dict.fromkeys(wanted) if one][:SERIES]
	if not wanted:
		frappe.throw(_("A record needs at least one series to be named by."))

	settings = frappe.get_doc("Document Naming Settings")
	settings.transaction_type = doctype
	settings.naming_series_options = "\n".join(wanted)
	settings.update_series()
	frappe.db.commit()
	return options(doctype)


def set_counter(doctype: str, prefix: str, value) -> list[dict]:
	"""Move a series' counter, which is the one destructive thing here.

	Frappe's own `update_series_start` writes a Version row for the change, and
	that is not bookkeeping for its own sake: a counter moved backwards will
	re-issue ids that already exist, and the only way anybody finds out why is
	that somebody wrote down who moved it.
	"""
	from frappe.model.naming import NamingSeries

	_reachable(doctype)

	prefix = str(prefix or "").strip()
	if prefix not in {one["prefix"] for one in options(doctype)}:
		frappe.throw(_("{0} is not a series on {1}.").format(prefix, doctype))

	try:
		value = int(value)
	except (TypeError, ValueError):
		frappe.throw(_("A counter is a whole number."))
	if value < 0:
		frappe.throw(_("A counter cannot go below zero."))

	series = NamingSeries(prefix)
	was = series.get_current_value()
	series.update_counter(value)

	version = frappe.new_doc("Version")
	version.ref_doctype = "Series"
	version.docname = series.get_prefix() or ".#"
	version.data = frappe.as_json({"changed": [["current", was, value]]})
	version.flags.ignore_links = True
	version.flags.ignore_permissions = True
	version.insert()

	frappe.db.commit()
	return options(doctype)


def preview(doctype: str, prefix: str) -> list[str]:
	"""The next few ids this series would issue.

	Frappe's own `get_preview`, against the doctype's last document where there
	is one — a series with `{customer}` in it means nothing without a record to
	read that from, and showing the template back is not a preview.
	"""
	from frappe.model.naming import NamingSeries

	_reachable(doctype)

	try:
		last = frappe.get_last_doc(doctype)
	except Exception:
		frappe.clear_last_message()
		last = None

	try:
		return NamingSeries(str(prefix or "")).get_preview(doc=last)
	except Exception as raised:
		frappe.clear_last_message()
		return [_("That series would not generate a name") + f": {raised!s}"]
