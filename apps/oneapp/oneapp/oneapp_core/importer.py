"""Bringing a customer's data with them, from a Frappe site that is still in use.

Every workspace that replaces something arrives with years of it, and the naive
answer — a script somebody runs once — gets it wrong twice. It runs once, and
the system it read from keeps moving, so the cutover becomes a night nobody
works and a morning of typing in whatever changed.

So this is an engine, and five properties are what make it one:

**Idempotent.** Every source row's target is remembered in `Import Identity`, so
a second run updates the record the first one made rather than making another.
That single table is also what lets a link resolve: an invoice's `party` becomes
the Customer an earlier step created out of the same source row.

**Incremental.** Each step keeps a watermark — the newest `modified` it has
taken across — and asks the source only for rows at or after it. Run it a month
before the cutover to rehearse, run it again at midnight, and the second run
carries only the delta. That is the "up to the last second" part, and it is
three lines rather than a feature.

**Resumable.** The watermark advances per committed batch, not per run. A step
that dies in the middle of two thousand rows resumes near where it stopped.

**Answerable.** A row that will not save is kept whole — what the source said,
what we made of it, and what refused it — as an `Import Issue`. A migration is
then a list to work through rather than a log to read.

**Rehearsable.** A dry run fetches, maps, resolves and validates, and commits
nothing. It is the only honest way to learn what a migration will do before it
does it, and the counts it reports are real.

Nothing here is about any one customer. A plan is data — steps, field maps,
value maps — so the next workspace arriving off its own Frappe site is a plan
and no code.

## The field map

Keyed by *target* fieldname, because what is being built is the target: read it
top to bottom and it is the record you end up with. Each value is one of:

    {"from": "party"}                                    copy a field across
    {"from": "type", "values": {...}, "default": "..."}  copy through a map
    {"from": "project", "link": "RUA Project"}           resolve to what an
                                                         earlier step made of
                                                         that source row
    {"const": "RUA Contracting"}                         the same on every row
    {"when": [["absent", "Absent"]], "default": "Present"}
                                                         the first of these
                                                         fields that is true
                                                         gives its value

A `link` that resolves to nothing is an issue on that row rather than a blank
saved quietly, because a link that silently did not arrive is the failure people
find months later in a report that is missing a third of its rows.

## One row over there, many rows here

The second most common shape a migration takes, after one-to-one. RUA keeps
attendance as one row per *day* holding a JSON object keyed by employee — 307
rows that have to become about twenty thousand — and a system that could only
map one row to one row would leave it behind, which is exactly why nothing in
that system can report on attendance.

A step says so with `fan_out`:

    {"from": "attendance_log", "shape": "map"}    an object: each key is a row
    {"from": "items", "shape": "list"}            an array: each item is a row

Each piece becomes its own target record, built from the parent's fields with
the piece's own merged over them and `__key` holding the key it came in under —
so the employee is `{"from": "__key", "link": "RUA Employee"}` and the day is
still `{"from": "date"}` off the parent.

Identity is `parent:key`, which keeps every promise the engine makes: a second
run updates the twenty thousand rather than making twenty thousand more, and a
day edited on the old system re-crosses only its own employees.
"""

import json
import re
from copy import deepcopy
from urllib.parse import quote, urlparse

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

# How many rows one request asks for. Frappe's own list endpoint is happy with
# far more; this is sized so a batch commits often enough that a crash costs
# seconds of work rather than minutes.
BATCH = 200

# What a step may spend before the queue takes it away. A migration is a long
# job by nature and the alternative to a long timeout is a partial import that
# looks finished.
TIMEOUT = 60 * 60

# Every field of a source row travels, because the field map decides what is
# read and a map edited later should not need a re-fetch to see a column it did
# not ask for last time.
ALL_FIELDS = '["*"]'


# --------------------------------------------------------------------------- #
# Reaching the other site
# --------------------------------------------------------------------------- #


def _endpoint(source) -> str:
	"""The source's base URL, checked before anything is sent to it.

	A customer types this in, which makes it the one place this feature can be
	pointed somewhere it should not go: an internal address, a metadata service,
	a neighbour's site on the same network. So it is https, it is a hostname
	rather than an address, and it is not a name that resolves inward.

	Not a substitute for the network's own rules, and not trying to be. It is
	the check that costs nothing and catches the mistake somebody makes by
	pasting the wrong thing.
	"""
	raw = (source.base_url or "").strip().rstrip("/")
	parsed = urlparse(raw)

	if parsed.scheme != "https":
		frappe.throw(_("A source has to be https. Credentials travel to it."))
	if not parsed.hostname or parsed.path or parsed.query:
		frappe.throw(_("A source is a host and nothing else, like https://old.example.com."))

	host = parsed.hostname.lower()
	if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".internal"):
		frappe.throw(_("That address is inside this network."))
	# An address rather than a name: the shapes that reach a metadata service or
	# a machine on the same subnet all look like one.
	if host.replace(".", "").replace(":", "").isdigit() or ":" in host:
		frappe.throw(_("A source is named by hostname, not by address."))

	return raw


def _get(source, path: str, params: dict) -> dict:
	"""One GET against the source, as the token's own user over there.

	`requests` rather than anything of Frappe's: this is an ordinary call to
	another site's REST API, and the framework's helpers are built for its own
	integrations with their own retry and logging opinions.
	"""
	import requests

	url = f"{_endpoint(source)}/api/{path}"
	secret = source.get_password("api_secret")
	answer = requests.get(
		url,
		params=params,
		headers={"Authorization": f"token {source.api_key}:{secret}"},
		timeout=60,
	)
	if answer.status_code == 401 or answer.status_code == 403:
		frappe.throw(_("The source refused the key. Check it is still valid over there."))
	answer.raise_for_status()
	return answer.json()


@frappe.whitelist()
def verify(source: str) -> dict:
	"""Ask the source who we are to it, and remember the answer.

	Worth its own button and its own field. An import runs as this user on the
	other site, so a key made from an account with half the permissions imports
	half the data and nothing anywhere says why — the rows it could not read
	simply were not in the answer.
	"""
	doc = frappe.get_doc("Import Source", source)
	doc.check_permission("write")

	try:
		who = _get(doc, "method/frappe.auth.get_logged_user", {}).get("message") or ""
	except Exception as raised:
		doc.db_set({"status": "Refused", "last_error": str(raised)[:500]})
		frappe.db.commit()
		return {"ok": False, "error": str(raised)}

	doc.db_set({
		"status": "Verified",
		"verified_as": who,
		"verified_on": now_datetime(),
		"last_error": "",
	})
	frappe.db.commit()
	return {"ok": True, "user": who}


@frappe.whitelist()
def preview(source: str, doctype: str, filters: str | None = None) -> dict:
	"""How many rows of one doctype are over there, and one of them.

	What somebody wants before writing a field map, and what the plan editor
	shows beside each step: a count to size the job, and a real row to map
	against rather than a memory of the schema.
	"""
	doc = frappe.get_doc("Import Source", source)
	doc.check_permission("read")

	params = {"limit_page_length": 1, "fields": ALL_FIELDS, "order_by": "modified desc"}
	if filters:
		params["filters"] = filters

	rows = _get(doc, f"resource/{doctype}", params).get("data") or []
	count = _get(doc, "method/frappe.client.get_count",
	             {"doctype": doctype, **({"filters": filters} if filters else {})})
	return {"count": count.get("message"), "row": rows[0] if rows else None}


def fetch(source, doctype: str, filters: list, start: int, length: int) -> list[dict]:
	"""One page of a doctype, oldest change first.

	`modified asc` is not a preference. The watermark is only safe if rows
	arrive in the order it advances through, and a page ordered any other way
	leaves a run that stops early having skipped rows it will never ask for
	again.
	"""
	return _get(source, f"resource/{doctype}", {
		"fields": ALL_FIELDS,
		"filters": json.dumps(filters),
		"order_by": "modified asc",
		"limit_start": start,
		"limit_page_length": length,
	}).get("data") or []


def attachments(source, doctype: str, name: str) -> list[dict]:
	"""What is attached to one record on the source.

	The half of a migration that gets forgotten and is the half people notice.
	Their eighty-two projects carry fifty architectural perspectives between
	them, their parties carry logos, their employees carry photographs and
	every compliance document is a scan of the paper — nine hundred and sixty
	files, and a system that arrives without them is a database rather than the
	company's records.
	"""
	return _get(source, "resource/File", {
		"fields": '["name","file_name","file_url","is_private"]',
		"filters": json.dumps([
			["attached_to_doctype", "=", doctype],
			["attached_to_name", "=", name],
		]),
		"limit_page_length": 0,
	}).get("data") or []


def download(source, file_url: str) -> bytes:
	"""One file's content, as the token's own user over there.

	A private file is only readable with the key, which is the whole reason
	this goes through the API rather than fetching the URL: half of what these
	people keep — passports, trade licences, signed invoices — is private, and
	an import that silently brought across only the public half would be worse
	than one that brought none.
	"""
	import requests

	answer = requests.get(
		f"{_endpoint(source)}{file_url}",
		headers={"Authorization": f"token {source.api_key}:{source.get_password('api_secret')}"},
		timeout=120,
	)
	answer.raise_for_status()
	return answer.content


def whole(source, doctype: str, name: str) -> dict:
	"""One document with its child tables.

	Frappe's list endpoint answers columns, and a child table is not a column —
	`fields=["*"]` on a list of quotations returns every one of them without a
	single line on it. So a step that maps child rows reads its rows twice: the
	list for the page and the watermark, then the document for what is inside
	it.

	One request per row, which is why it happens only where a step says it
	needs to: it is the difference between five quotations and twenty thousand
	attendance records.
	"""
	return _get(source, f"resource/{doctype}/{quote(str(name))}", {}).get("data") or {}


# --------------------------------------------------------------------------- #
# Turning one row into another
# --------------------------------------------------------------------------- #


class Unresolved(Exception):
	"""A link that pointed at something no step has made yet.

	Its own exception because it is not a bad row — it is a plan whose steps are
	in the wrong order, and the row is fine and will import once they are not.
	The message says which link, because that is the whole diagnosis.
	"""


def build(row: dict, field_map: dict, plan: str) -> dict:
	"""One source row as the values of one target record.

	Every rule is explicit. There is deliberately no "copy anything whose name
	matches": two systems that happen to share a fieldname mean the same thing
	about a third of the time, and the third that do not are the ones nobody
	notices until the numbers are wrong.
	"""
	values = {}

	for target, rule in (field_map or {}).items():
		if not isinstance(rule, dict):
			# The short form, because `{"customer_name": "party"}` is what
			# somebody writes first and refusing it teaches nothing.
			rule = {"from": rule}

		if "const" in rule:
			# Copied, not shared. A constant that is a list of child rows would
			# otherwise be the same objects on every record the run makes, and
			# whatever the first document's controller wrote into them would be
			# what the second one started from.
			said = rule["const"]
			values[target] = deepcopy(said) if isinstance(said, list | dict) else said
			continue

		if "rows" in rule:
			# A child table. The target's own rows, built out of a list on the
			# source with a field map of their own — the same four rule shapes,
			# because a line on an invoice is a record like any other and
			# nothing about it wants a second vocabulary.
			values[target] = [
				build(one, rule.get("map") or {}, plan)
				for one in _lines(row, rule["rows"])
			]
			continue

		if "when" in rule:
			# The first of these fields that is true gives its value. For the
			# columns a bespoke system keeps as three booleans where a real one
			# keeps a status — present, late, absent — which cannot be a `from`
			# because the answer is not in any one of them.
			values[target] = next(
				(said for field, said in rule["when"] if row.get(field)),
				rule.get("default"),
			)
			continue

		said = row.get(rule.get("from"))

		if "pick" in rule:
			# One entry out of a list the old system denormalised onto the row.
			# Their project carries every party on it — client, consultant, four
			# suppliers — as JSON with a `type` on each, and the customer is
			# whichever one says Client. Without this the field is unreachable:
			# it is not a column and it is not a child table.
			said = _pick(said, rule["pick"], rule.get("take"))

		if rule.get("link"):
			if said in (None, ""):
				continue
			found = resolve(plan, rule["link"], said)
			if not found:
				raise Unresolved(
					f"{target}: nothing here yet for {rule['link']} {said}. "
					"Run that step first, or move it earlier in the plan."
				)
			values[target] = found
			continue

		if rule.get("number"):
			# What somebody typed, as a number. Their widths are strings —
			# `"200.0 cm"` — because the old form had one box and no unit, and
			# a system that keeps a measurement as prose cannot add two of
			# them. Deliberately narrow: the leading number, or nothing.
			said = _number(said)

		if "values" in rule:
			said = rule["values"].get(said, rule.get("default", said))

		# A second field to try before giving up. For the columns a bespoke
		# system left optional that this one requires: two of their employees
		# have no joining date, and the date the record was made is wrong by
		# however long the old system lagged and is the only date there is.
		if said in (None, "") and "default_from" in rule:
			said = row.get(rule["default_from"])

		if said in (None, "") and "default" in rule:
			said = rule["default"]

		if rule.get("into"):
			# A small closed vocabulary the old system kept as free text and
			# this one keeps as records: fourteen job titles, two emirates,
			# three branches. Deliberately per-rule and not a default — the
			# same mechanism pointed at a quotation's line codes would invent
			# an item master out of a year of typing.
			if said in (None, ""):
				continue
			said = vocabulary(rule["into"], said, rule.get("with"))

		values[target] = said

	return values


def vocabulary(doctype: str, said, extra: dict | None = None) -> str:
	"""One record of a small vocabulary, made if it is not there.

	Named by the field the doctype names itself after, which is what makes this
	answerable at all: Designation is `field:designation_name`, Territory is
	`field:territory_name`, and a doctype named any other way is not a
	vocabulary and does not belong behind this rule.

	Inserted as the operator, like everything else the engine writes: an import
	that could create what its operator cannot is a way around every permission
	on the site.
	"""
	if frappe.db.exists(doctype, said):
		return said

	named = frappe.get_meta(doctype).autoname or ""
	if not named.startswith("field:"):
		frappe.throw(_("{0} is not named after a field, so it cannot be filled in "
		               "from a value.").format(doctype))

	doc = frappe.get_doc({"doctype": doctype, **(extra or {}),
	                      named.split(":", 1)[1]: said}).insert()
	return doc.name


# A `rows` rule that says this rather than a fieldname builds one child row out
# of the parent. For a document whose amount is a header field because it was
# never itemised — a progress invoice is one number against a contract — and
# which the target doctype nonetheless requires a line for.
SELF = "__self"


def _lines(row: dict, rows: str) -> list[dict]:
	return [row] if rows == SELF else (row.get(rows) or [])


def maps_children(field_map: dict) -> bool:
	"""Whether anything in this map reads a child table off the source.

	`__self` is not one: it builds a row out of the parent, which the list
	endpoint already answered, so a step that only does that does not need the
	second read per row.
	"""
	return any(
		isinstance(rule, dict) and rule.get("rows") not in (None, SELF)
		for rule in (field_map or {}).values()
	)


def _pick(said, matching: dict, take: str | None):
	"""The first item of a list that matches, or nothing.

	Nothing rather than the first item: a project with no consultant on it has
	no consultant, and handing back whoever happened to be listed first is how
	a migration invents relationships.
	"""
	if said in (None, ""):
		return None

	held = frappe.parse_json(said)
	if not isinstance(held, list):
		raise ValueError("`pick` needs a list, and this is not one")

	found = next(
		(one for one in held
		 if isinstance(one, dict)
		 and all(one.get(key) == value for key, value in (matching or {}).items())),
		None,
	)
	if found is None:
		return None
	return found.get(take) if take else found


def _number(said):
	"""The leading number in whatever this is, or None."""
	if said in (None, ""):
		return None
	if isinstance(said, int | float):
		return said
	found = re.search(r"-?\d+(?:\.\d+)?", str(said))
	return float(found.group()) if found else None


def explode(row: dict, rule: dict | None) -> list[tuple[str, dict]]:
	"""One source row as the several target rows it actually is.

	Answers `[(key, row)]` either way, so the caller has one loop and not two:
	a step with no `fan_out` is one piece keyed by the row's own name, which is
	exactly the identity it had before this existed.

	A piece's key is the row's name *and* the piece's own, because neither
	alone identifies it. Keyed on the piece alone, a month of attendance keyed
	by employee is one record per employee overwritten once a day: 20,229 rows
	read and 71 kept, and the run reports twenty thousand updates as if that
	were the point of them.

	The piece's own fields are merged *over* the parent's rather than under
	them. A day's row carries `name`, `date` and `modified`; an employee's entry
	inside it carries `present` and `overtime`. Where both name something, the
	inner one is the more specific and wins.
	"""
	if not rule:
		return [(str(row.get("name")), row)]

	held = row.get(rule.get("from"))
	if held in (None, ""):
		return []

	held = frappe.parse_json(held)

	if rule.get("shape") == "list":
		if not isinstance(held, list):
			raise ValueError(f"`{rule['from']}` is not a list")
		# Keyed by position, because a list has no other stable name — and a
		# stable name is what makes a second run an update.
		return [
			(f"{row.get('name')}:{at}",
			 {**row, **(one if isinstance(one, dict) else {"value": one}),
			  "__key": str(at)})
			for at, one in enumerate(held)
		]

	if not isinstance(held, dict):
		raise ValueError(f"`{rule['from']}` is not an object")

	return [
		(f"{row.get('name')}:{key}",
		 {**row, **(one if isinstance(one, dict) else {"value": one}),
		  "__key": str(key)})
		for key, one in held.items()
	]


def resolve(plan: str, source_doctype: str, source_name: str) -> str:
	"""What this plan made of one source row, or nothing.

	The whole of link resolution, and the reason it is a table rather than a
	naming convention: a source row named by hash whose target is named after a
	field has no other way back to itself.
	"""
	return frappe.db.get_value(
		"Import Identity",
		{"plan": plan, "source_doctype": source_doctype, "source_name": source_name},
		"target_name",
	)


# --------------------------------------------------------------------------- #
# Doing it
# --------------------------------------------------------------------------- #


@frappe.whitelist()
def start(plan: str, dry_run: int = 0) -> str:
	"""Queue a run of one plan, and hand back its name to watch.

	Queued rather than run: a migration is minutes to hours and a request that
	waits for one is a request that times out half way through, leaving a run
	nobody is watching and a browser that says it failed.
	"""
	doc = frappe.get_doc("Import Plan", plan)
	doc.check_permission("write")

	if not doc.is_active:
		frappe.throw(_("That plan is switched off."))

	running = frappe.db.exists("Import Run", {"plan": plan, "status": ("in", ("Queued", "Running"))})
	if running:
		# Two runs of one plan race each other through the same identities, and
		# what they produce is not the same as either of them alone.
		frappe.throw(_("{0} is already running.").format(running))

	run = frappe.get_doc({
		"doctype": "Import Run",
		"plan": plan,
		"dry_run": cint(dry_run),
		"status": "Queued",
		"steps": [
			{"source_doctype": s.source_doctype, "target_doctype": s.target_doctype,
			 "status": "Queued" if s.enabled else "Skipped"}
			for s in doc.steps
		],
	}).insert()
	frappe.db.commit()

	frappe.enqueue(
		"oneapp.oneapp_core.importer.execute",
		queue="long",
		timeout=TIMEOUT,
		run=run.name,
		# The job runs as whoever pressed it, so what an import may create is
		# what that person may create. An import that could write what its
		# operator cannot is a way around every permission on the site.
		user=frappe.session.user,
	)
	return run.name


def execute(run: str, user: str | None = None):
	"""The job: every enabled step of the plan, in the order it declares them.

	Order is the author's, and it is dependency order — parties before the
	invoices that link to them. Nothing here sorts it: a plan that got it wrong
	says so as unresolved links on real rows, which is a better error than a
	guess at what depends on what.
	"""
	if user:
		frappe.set_user(user)

	doc = frappe.get_doc("Import Run", run)
	plan = frappe.get_doc("Import Plan", doc.plan)
	source = frappe.get_doc("Import Source", plan.source)

	doc.db_set({"status": "Running", "started_on": now_datetime()})
	frappe.db.commit()

	# A rehearsal is the real run inside a transaction that is thrown away.
	# Nothing else is a rehearsal: validating a document in isolation cannot
	# resolve a link to a record an earlier step would have made, so every step
	# after the first reported failures that only a rehearsal has. Issues are
	# kept in memory instead of written, because the rollback would take them
	# with everything else.
	held: list | None = [] if doc.dry_run else None

	# Paired by position, not by source doctype. Keyed by name, two steps off
	# one source — a party table split into customers and suppliers, the
	# ordinary reason to have two — collapse to whichever came last, and the
	# other silently never runs: seventy-five customers that the run reports as
	# done and never looked at. The run's rows are made from the plan's in
	# order by `start`, so position is the identity; anything else means the
	# plan was edited under the run, which is worth stopping for.
	if len(doc.steps) != len(plan.steps):
		frappe.throw(_("{0} changed since this run was queued.").format(plan.name))

	try:
		for row, step in zip(doc.steps, plan.steps, strict=True):
			if (row.source_doctype, row.target_doctype) != (step.source_doctype,
			                                                step.target_doctype):
				frappe.throw(_("{0} changed since this run was queued.").format(plan.name))
			if not step.enabled:
				continue
			_step(doc, plan, source, step, row, held)
	except Exception:
		doc.reload()
		doc.db_set({"status": "Failed", "finished_on": now_datetime(),
		            "error": frappe.get_traceback(with_context=False)[-500:]})
		frappe.db.commit()
		raise

	counted = [(r.name, r.seen, r.created, r.updated, r.failed) for r in doc.steps]

	if doc.dry_run:
		# Everything the rehearsal wrote, undone — and then the only two things
		# worth keeping written again: what it counted, and what it refused.
		frappe.db.rollback()
		for name, seen, created, updated, failed in counted:
			frappe.db.set_value("Import Run Step", name, {
				"status": "Done", "seen": seen, "created": created,
				"updated": updated, "failed": failed,
			}, update_modified=False)
		for said in held:
			frappe.get_doc(said).insert(ignore_permissions=True)

	doc.reload()
	doc.db_set({
		"status": "Done",
		"finished_on": now_datetime(),
		"total_seen": sum(cint(r.seen) for r in doc.steps),
		"total_created": sum(cint(r.created) for r in doc.steps),
		"total_updated": sum(cint(r.updated) for r in doc.steps),
		"total_failed": sum(cint(r.failed) for r in doc.steps),
	})
	frappe.db.commit()


def _step(run, plan, source, step, row, held: list | None = None):
	"""One doctype, a page at a time, from the watermark forward."""
	counts = {"seen": 0, "created": 0, "updated": 0, "failed": 0}
	_mark(row, {"status": "Running", "watermark_from": step.watermark})

	filters = json.loads(step.filters) if step.filters else []
	if step.watermark:
		# `>=` and not `>`, deliberately. Rows that share the boundary's exact
		# `modified` would otherwise be dropped by the next run — a second of
		# records lost at a page edge, silently. Re-reading them costs an update
		# apiece, and updating is free because every row is an identity.
		filters = filters + [[step.source_doctype, "modified", ">=", str(step.watermark)]]

	field_map = json.loads(step.field_map or "{}")
	fan_out = json.loads(step.fan_out) if step.fan_out else None
	deep = maps_children(field_map)
	start = 0
	# A string, always. The watermark comes back out of the database as a
	# datetime and a row's `modified` arrives from the API as text, and `max`
	# over the two raises — so the *first* run worked, every time, and the
	# second one died before it read a row. Which is the run that matters:
	# incremental is the whole promise.
	newest = str(step.watermark) if step.watermark else None

	while True:
		page = fetch(source, step.source_doctype, filters, start, BATCH)
		if not page:
			break

		for said in page:
			# A step that maps child rows reads its rows twice — see `whole`.
			# Inside the row loop rather than around it so one document that
			# will not load is one issue, not a dead page.
			if deep:
				try:
					said = {**said, **whole(source, step.source_doctype, said.get("name"))}
				except Exception as raised:
					counts["seen"] += 1
					counts["failed"] += 1
					_issue(run, step, said, raised)
					newest = max(filter(None, (newest, said.get("modified"))), default=newest)
					continue

			# `seen` counts source rows and not target ones: it is what the
			# source has, and a number that grew twenty times faster than the
			# thing being read would be unreadable as progress.
			counts["seen"] += 1
			try:
				pieces = explode(said, fan_out)
			except Exception as raised:
				counts["failed"] += 1
				_issue(run, step, said, raised)
				pieces = []

			for key, piece in pieces:
				# One savepoint per row. A failed insert leaves the transaction
				# dirty, and the blanket rollback this used to do took the rest
				# of the page with it — up to a hundred and ninety-nine records
				# already counted as created and then quietly discarded.
				mark = f"imp{counts['seen']}_{counts['created']}"
				frappe.db.savepoint(mark)
				try:
					made = build(piece, field_map, plan.name)
					# `key` and not `piece["name"]`: every piece of one row
					# shares the parent's name, and an identity keyed on that
					# would have twenty thousand rows overwrite each other.
					what = _write(plan, step, key, piece, made, source, field_map)
				except Exception as raised:
					frappe.db.rollback(save_point=mark)
					counts["failed"] += 1
					_issue(run, step, piece, raised, held)
				else:
					frappe.db.release_savepoint(mark)
					counts[what] += 1

			newest = max(filter(None, (newest, said.get("modified"))), default=newest)

		# Per page, not per run. This is what "resumable" means: a step killed
		# at row nineteen hundred restarts near there rather than at one.
		if not run.dry_run:
			frappe.db.set_value("Import Step", step.name, "watermark", newest,
			                    update_modified=False)
		_mark(row, {**counts, "watermark_to": newest})
		if not run.dry_run:
			frappe.db.commit()

		if len(page) < BATCH:
			break
		start += BATCH

	if not run.dry_run:
		frappe.db.set_value("Import Step", step.name, "last_run", run.name,
		                    update_modified=False)
	_mark(row, {"status": "Done", **counts, "watermark_to": newest})
	if not run.dry_run:
		frappe.db.commit()


def _write(plan, step, key: str, said: dict, made: dict, source=None,
           field_map: dict | None = None) -> str:
	"""Insert or update the one record this source row is, and remember which.

	Through `get_doc` and `save`, never a direct write: an imported Sales
	Invoice that skipped its own controller is a row in a table rather than a
	document, and the ledger behind it does not exist. A migration that beats
	validation has imported the shape of the data and not the data.
	"""
	existing = resolve(plan.name, step.source_doctype, key)

	if existing and frappe.db.exists(step.target_doctype, existing):
		doc = frappe.get_doc(step.target_doctype, existing)
		doc.update(made)
		doc.save()
		_remember(plan, step, key, doc.name)
		_attach(source, step, said, doc, field_map)
		return "updated"

	doc = frappe.get_doc({"doctype": step.target_doctype, **made}).insert()
	_remember(plan, step, key, doc.name)
	# After the insert, not before: a File names the record it hangs on, and
	# the record has no name until it exists.
	_attach(source, step, said, doc, field_map)
	return "created"


def _attach(source, step, said: dict, doc, field_map: dict | None):
	if source is None:
		return
	_point_at_ours(doc, said, field_map or {}, carry(source, step, said, doc, field_map or {}))


def carry(source, step, said: dict, doc, field_map: dict) -> dict:
	"""Bring one row's files across and hang them on the record we made.

	Two ways to ask, because there are two kinds. A step saying `carry_files`
	wants everything attached over there attached here — the perspectives on a
	project, the scan behind a compliance document. A *rule* saying `"file":
	true` wants one named field that holds a path rather than a value: a party's
	logo, an employee's photograph, and the field has to end up pointing at our
	copy rather than at a URL on a site the customer is about to switch off.

	Answers what it copied, keyed by the path it had over there, so the rules
	can be pointed at the new one.
	"""
	wanted = {
		rule["from"] for rule in (field_map or {}).values()
		if isinstance(rule, dict) and rule.get("file") and rule.get("from")
	}
	named = {said.get(one) for one in wanted} - {None, ""}

	if not cint(getattr(step, "carry_files", 0)) and not named:
		return {}

	# Already here, from a previous run. Matched on the name it had over there,
	# which is what makes a second run a no-op rather than a second copy of
	# every photograph in the company.
	here = {
		row.file_name
		for row in frappe.get_all("File",
		                          filters={"attached_to_doctype": doc.doctype,
		                                   "attached_to_name": doc.name},
		                          fields=["file_name"])
	}

	made = {}
	for one in attachments(source, step.source_doctype, said.get("name")):
		if not cint(getattr(step, "carry_files", 0)) and one["file_url"] not in named:
			continue
		if one["file_name"] in here:
			# Still worth answering: a rule pointing at it needs our URL even
			# on a run that copied nothing.
			made[one["file_url"]] = frappe.db.get_value(
				"File", {"attached_to_doctype": doc.doctype,
				         "attached_to_name": doc.name,
				         "file_name": one["file_name"]}, "file_url")
			continue

		# Assigned and then inserted, rather than reading what `insert` hands
		# back: what this needs is the URL Frappe gave the copy, and that is on
		# the document either way.
		file = frappe.get_doc({
			"doctype": "File",
			"file_name": one["file_name"],
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"is_private": cint(one.get("is_private")),
			"content": download(source, one["file_url"]),
		})
		file.insert(ignore_permissions=True)
		made[one["file_url"]] = file.file_url

	return made


def _point_at_ours(doc, said: dict, field_map: dict, files: dict):
	"""Repoint the fields that hold a path at the copy we just made.

	A logo whose URL is on the site the customer is switching off is a broken
	image the week after the migration, and nobody looks at a logo until then.
	"""
	for target, rule in (field_map or {}).items():
		if not (isinstance(rule, dict) and rule.get("file")):
			continue
		found = files.get(said.get(rule.get("from")))
		if found and doc.get(target) != found:
			doc.db_set(target, found, update_modified=False)


def _remember(plan, step, source_name: str, target_name: str):
	"""The identity row, written once and read by every link after it."""
	existing, was = frappe.db.get_value(
		"Import Identity",
		{"plan": plan.name, "source_doctype": step.source_doctype, "source_name": source_name},
		["name", "target_doctype"],
	) or (None, None)
	if existing and was and was != step.target_doctype:
		# Two steps off one source doctype, both catching this row. Silently
		# rewriting the identity would repoint every link that already resolved
		# through it, so the row fails and the plan's filters get fixed.
		frappe.throw(
			f"{step.source_doctype} {source_name} is already {was} "
			f"{frappe.db.get_value('Import Identity', existing, 'target_name')} in this plan — "
			f"two steps claim it. Narrow one step's filters."
		)
	if existing:
		frappe.db.set_value("Import Identity", existing,
		                    {"target_name": target_name, "last_seen": now_datetime()},
		                    update_modified=False)
		return

	frappe.get_doc({
		"doctype": "Import Identity",
		"plan": plan.name,
		"source_doctype": step.source_doctype,
		"source_name": source_name,
		"target_doctype": step.target_doctype,
		"target_name": target_name,
		"last_seen": now_datetime(),
	}).insert(ignore_permissions=True)


def _issue(run, step, said: dict, raised: Exception, held: list | None = None):
	"""One row that would not import, kept whole.

	The payload as well as the error, because the source site will have moved on
	by the time anybody reads this and a message with no row attached is a
	question nobody can answer.

	`held` is a rehearsal: the run it belongs to is about to be rolled back, so
	writing this now would throw it away with everything else.
	"""
	issue = {
		"doctype": "Import Issue",
		"run": run.name,
		"source_doctype": step.source_doctype,
		"source_name": said.get("name"),
		"error": f"{type(raised).__name__}: {raised}"[:500],
		"payload": frappe.as_json(said),
	}
	if held is not None:
		held.append(issue)
		return
	frappe.get_doc(issue).insert(ignore_permissions=True)


def _mark(row, values: dict):
	"""Progress onto the run's own step row, without touching the parent.

	`db_set` on a child rather than saving the run: a run being watched is
	reloaded every few seconds, and saving the parent to move a counter would
	file a Version per page of every step.
	"""
	for key, value in values.items():
		frappe.db.set_value("Import Run Step", row.name, key, value,
		                    update_modified=False)
		row.set(key, value)


@frappe.whitelist()
def progress(run: str) -> dict:
	"""Where a run has got to, for something watching it."""
	doc = frappe.get_doc("Import Run", run)
	doc.check_permission("read")
	return {
		"status": doc.status,
		"dry_run": doc.dry_run,
		"started_on": doc.started_on,
		"finished_on": doc.finished_on,
		"error": doc.error,
		"steps": [
			{"source_doctype": r.source_doctype, "target_doctype": r.target_doctype,
			 "status": r.status, "seen": r.seen, "created": r.created,
			 "updated": r.updated, "failed": r.failed}
			for r in doc.steps
		],
		"issues": frappe.db.count("Import Issue", {"run": run, "status": "Open"}),
	}


# --------------------------------------------------------------------------- #
# The one screen
#
# What the person leaving their old system sees: where it is, what will come
# across, and two buttons — rehearse it, then do it. One request rather than
# five, because the panel is one picture and five requests is five spinners.
# --------------------------------------------------------------------------- #


@frappe.whitelist(methods=["GET"])
def console() -> dict:
	"""Everything the import panel draws, in one answer."""
	if not frappe.has_permission("Import Plan", "read"):
		frappe.throw(_("Not yours to see."), frappe.PermissionError)

	sources = frappe.get_all(
		"Import Source",
		fields=["name", "base_url", "api_key", "status", "verified_as",
		        "verified_on", "last_error"],
		order_by="creation asc",
	)

	plans = []
	for plan in frappe.get_all("Import Plan", fields=["name", "source", "is_active"],
	                           order_by="creation asc"):
		doc = frappe.get_doc("Import Plan", plan["name"])
		last = frappe.get_all(
			"Import Run", filters={"plan": plan["name"]},
			fields=["name", "status", "dry_run", "started_on", "finished_on",
			        "total_seen", "total_created", "total_updated", "total_failed"],
			order_by="creation desc", limit=1,
		)
		plans.append({
			**plan,
			"steps": [
				{"source_doctype": s.source_doctype, "target_doctype": s.target_doctype,
				 "enabled": s.enabled, "watermark": s.watermark}
				for s in doc.steps
			],
			"last_run": last[0] if last else None,
			# The whole promise, in one boolean: a plan every step of which has a
			# watermark has been across once, so the next run is a top-up rather
			# than the move.
			"carried": bool(doc.steps) and all(s.watermark for s in doc.steps),
		})

	# What this app ships, this workspace has a space for, and nobody has set
	# up yet. Without it the panel's first state is an empty one — nothing to
	# import and no way to say otherwise — and the whole "one button" claim
	# rests on somebody having installed a plan from a Python shell.
	#
	# Filtered by space, because a shipped plan is one customer's own migration
	# and offering it to every workspace would be offering to fill their books
	# with a stranger's.
	from oneapp.oneapp_core import sync
	from oneapp.oneapp_core.plans import shipped

	installed = {plan["name"] for plan in plans}
	here = {space.get("space_code") for space in sync.state().get("spaces") or []}
	offered = [
		one for one in shipped()
		if one["title"] not in installed and one["space"] in here
	]

	return {"sources": sources, "plans": plans, "shipped": offered}


@frappe.whitelist()
def install_plan(plan: str, source: str) -> str:
	"""Set up one of the plans this app ships, against a connection.

	Its own endpoint rather than a step in `start`: installing writes custom
	fields and seed records, and doing that as a side effect of pressing Run
	would make the first run mean something the second one does not.
	"""
	if not frappe.has_permission("Import Plan", "create"):
		frappe.throw(_("Not yours to set up."), frappe.PermissionError)

	frappe.get_doc("Import Source", source).check_permission("read")

	from oneapp.oneapp_core.plans import PLANS, install

	if plan not in PLANS:
		frappe.throw(_("There is no plan called {0}.").format(plan))

	return install(plan, source)


@frappe.whitelist()
def save_source(name: str, base_url: str, api_key: str, api_secret: str | None = None) -> dict:
	"""The customer's own credentials for their own old system.

	The secret is written only when one is given, so an edit to the URL does not
	need it retyped — and it is never sent back out: `console` returns the key
	and never the secret, which is what a Password field is for.
	"""
	known = frappe.db.exists("Import Source", name)
	doc = frappe.get_doc("Import Source", name) if known else frappe.new_doc("Import Source")
	doc.check_permission("write" if known else "create")

	doc.source_name = name
	doc.base_url = base_url
	doc.api_key = api_key
	if api_secret:
		doc.api_secret = api_secret
	doc.save()
	frappe.db.commit()
	return {"name": doc.name}


@frappe.whitelist(methods=["GET"])
def issues(run: str, limit: int = 50) -> list[dict]:
	"""The rows that would not come across, newest first."""
	frappe.get_doc("Import Run", run).check_permission("read")
	return frappe.get_all(
		"Import Issue",
		filters={"run": run, "status": "Open"},
		fields=["name", "source_doctype", "source_name", "error", "payload"],
		order_by="creation desc",
		limit_page_length=cint(limit),
	)


# --------------------------------------------------------------------------- #
# Checking a plan before running it
#
# A fourteen-step field map is a document nobody can read for correctness, and
# the mistakes in one are all quiet: a source field renamed since somebody wrote
# the map, a target field that does not exist on this site's version, a value
# map that covers four of the five values actually in the data, a link resolved
# against a step that runs later.
#
# None of those fails loudly. The first three drop a column, the fourth files an
# issue per row — and all of them are found after the run, in a report somebody
# reads a week later and disbelieves.
#
# So the plan is checked against *both ends* before it is run: the source's own
# metadata over the wire, and this site's own metadata locally. It reads
# everything and writes nothing, which makes it free to run as often as anybody
# likes — and it is what the Check button beside Rehearse does.
# --------------------------------------------------------------------------- #

# How many rows to look at when working out which values a value map has to
# cover. Enough to meet the long tail of a real column, cheap enough to run on
# a button.
SAMPLE = 500

# How many documents a check will read whole looking for one with lines on it.
# Small on purpose: this is the difference between a check that takes a second
# and one that re-reads the source.
LOOK = 8


@frappe.whitelist()
def check(plan: str) -> dict:
	"""Everything wrong with a plan that can be known without running it."""
	doc = frappe.get_doc("Import Plan", plan)
	doc.check_permission("read")
	source = frappe.get_doc("Import Source", doc.source)

	# What each step will have made by the time a later one resolves a link
	# against it. Built as the steps are walked, in their declared order, which
	# is exactly the order the run walks them in.
	made = set()
	# The names each source doctype's sample held, so a second step off the
	# same doctype can be asked the only question worth asking about it: do
	# these two steps claim the same rows?
	seen: dict[str, set] = {}
	found = []

	for step in doc.steps:
		if not step.enabled:
			made.add(step.source_doctype)
			continue
		found.append(_check_step(source, doc, step, made, seen))
		made.add(step.source_doctype)

	return {
		"plan": plan,
		"steps": found,
		"problems": sum(len(s["problems"]) for s in found),
		"warnings": sum(len(s["warnings"]) for s in found),
	}


def _check_step(source, plan, step, made: set, seen: dict | None = None) -> dict:
	"""One step, against the source's schema and this site's."""
	problems, warnings = [], []

	try:
		field_map = json.loads(step.field_map or "{}")
	except ValueError as raised:
		return {"source_doctype": step.source_doctype, "target_doctype": step.target_doctype,
		        "problems": [f"the field map is not JSON: {raised}"], "warnings": [],
		        "source_rows": None}

	seen = seen if seen is not None else {}

	try:
		filters = json.loads(step.filters or "[]")
	except ValueError as raised:
		return {"source_doctype": step.source_doctype, "target_doctype": step.target_doctype,
		        "problems": [f"the filters are not JSON: {raised}"], "warnings": [],
		        "source_rows": None}

	theirs, rows = _their_fields(source, step.source_doctype, filters, problems)
	ours = _our_fields(step.target_doctype, problems)

	# One whole document, where the map reads child rows. The list endpoint
	# does not answer them, so without this every `rows` rule would be checked
	# against a row that cannot have them and reported missing — and the field
	# names inside the lines would never be checked at all.
	if rows and maps_children(field_map):
		try:
			rows[0] = _one_with_lines(source, step, rows, field_map)
			theirs = set(rows[0])
		except Exception as raised:
			problems.append(f"could not read one whole {step.source_doctype}: {raised}")

	# Two steps off one source doctype is ordinary — a party table holding both
	# customers and suppliers is the usual reason — and fine while their
	# filters are disjoint. Where they are not it is quietly wrong: `resolve`
	# is keyed on the source doctype alone, so a row caught by both resolves to
	# whichever step ran last, and `_remember` then refuses the row mid-run.
	# Which is why this asks the rows rather than the schema.
	#
	# Keyed by target as well, because two steps into the *same* target are a
	# second pass rather than an ambiguity: a project's parent is another
	# project, so the link cannot resolve until every project exists, and the
	# only honest way to write that is to go round twice.
	names = {row.get("name") for row in (rows or [])} - {None}
	both = sorted(names & seen.get((step.source_doctype, step.target_doctype), set()))
	if both:
		warnings.append(
			f"{len(both)} row(s) of {step.source_doctype} are claimed by an earlier step "
			f"too — {', '.join(both[:3])}. Narrow one step's filters; a row cannot "
			"become two things."
		)
	key = (step.source_doctype, step.target_doctype)
	seen[key] = names | seen.get(key, set())

	# A fan-out changes what the field map may name, so it is read first: the
	# fields inside one piece are not fields of the source doctype, and
	# checking the map against the parent's columns alone would report every
	# one of them missing.
	fan_out, pieces = _check_fan_out(step, rows, theirs, problems)
	if fan_out and pieces:
		theirs = set(pieces[0][1])

	for target, rule in field_map.items():
		if not isinstance(rule, dict):
			rule = {"from": rule}

		if ours is not None and target not in ours:
			problems.append(f"{step.target_doctype} has no field `{target}`")

		if "const" in rule:
			continue

		if "rows" in rule:
			# The list itself, and then the fields inside one of its lines.
			# Checking only that the list is there would pass a map naming
			# `unit_price` on a table whose column is `rate`, which is every
			# line silently blank.
			if (theirs is not None and rule["rows"] != SELF
					and rule["rows"] not in theirs):
				problems.append(f"`{target}` reads `{rule['rows']}`, which is not there")
				continue
			lines = _lines(rows[0], rule["rows"]) if rows else []
			if not lines:
				warnings.append(
					f"`{target}` reads `{rule['rows']}`, and the row checked has no lines "
					"in it — the fields inside are unchecked"
				)
				continue
			for inner, said in (rule.get("map") or {}).items():
				if isinstance(said, dict) and ("const" in said or "rows" in said):
					continue
				field = said.get("from") if isinstance(said, dict) else said
				if field and field not in lines[0]:
					problems.append(
						f"`{target}.{inner}` reads `{field}`, which is not on a line"
					)
			continue

		if "when" in rule:
			for field, _said in rule["when"]:
				if theirs is not None and field not in theirs:
					problems.append(f"`{target}` asks about `{field}`, which is not there")
			continue

		said = rule.get("from")
		if not said:
			problems.append(f"`{target}` names no source field and no constant")
			continue
		if theirs is not None and said not in theirs:
			problems.append(f"{step.source_doctype} has no field `{said}`")

		if rule.get("link") and rule["link"] not in made:
			# Not a warning. A link resolved before its step has run finds
			# nothing on every row, and the run files one issue per record
			# rather than saying the plan is in the wrong order.
			problems.append(
				f"`{target}` resolves against {rule['link']}, which this plan "
				"runs later or not at all"
			)

		# The quiet one: a value map that covers what somebody remembered rather
		# than what is in the column. A warning and not a problem, because
		# `default` may be exactly the intent.
		if "values" in rule and rows:
			unseen = sorted({
				str(row.get(said)) for row in rows
				if row.get(said) not in (None, "") and row.get(said) not in rule["values"]
			})
			if unseen and "default" not in rule:
				warnings.append(
					f"`{said}` also holds {', '.join(unseen[:6])} — "
					"unmapped and with no default, so they cross over as-is"
				)

	return {
		"source_doctype": step.source_doctype,
		"target_doctype": step.target_doctype,
		"problems": problems,
		"warnings": warnings,
		"source_rows": len(rows) if rows is not None else None,
	}


def _one_with_lines(source, step, rows: list, field_map: dict) -> dict:
	"""A whole document out of the sample, preferring one that has lines on it.

	The first row is the obvious one to read and often the wrong one: their
	oldest purchase order has no items on it at all, and checking against that
	one says nothing about the map and warns about the data. So a few are tried
	and the first with lines wins — `LOOK` of them, because this is a check and
	not a second import.
	"""
	tables = [rule["rows"] for rule in field_map.values()
	          if isinstance(rule, dict) and rule.get("rows") not in (None, SELF)]
	first = None

	for row in rows[:LOOK]:
		found = {**row, **whole(source, step.source_doctype, row.get("name"))}
		first = first if first is not None else found
		if any(found.get(table) for table in tables):
			return found

	return first if first is not None else rows[0]


def _check_fan_out(step, rows, theirs, problems: list):
	"""The `fan_out` rule, and one real row put through it.

	Exploding a sample is the only honest check: the rule names a field holding
	JSON, and whether that JSON is the shape it claims cannot be known from a
	schema. A step that says `map` over a column holding an array fails on every
	row, and this is where that is cheap to find out.
	"""
	if not step.fan_out:
		return None, None

	try:
		rule = json.loads(step.fan_out)
	except ValueError as raised:
		problems.append(f"the fan-out is not JSON: {raised}")
		return None, None

	if theirs is not None and rule.get("from") not in theirs:
		problems.append(f"the fan-out reads `{rule.get('from')}`, which is not there")
		return rule, None

	if not rows:
		return rule, None

	try:
		pieces = explode(rows[0], rule)
	except Exception as raised:
		problems.append(f"the fan-out does not fit the data: {raised}")
		return rule, None

	if not pieces:
		problems.append(f"the first row's `{rule.get('from')}` is empty, so nothing fans out")
	return rule, pieces


def _their_fields(source, doctype: str, filters: list, problems: list):
	"""The source's own column names, and a sample of its rows.

	Read off the data rather than off `DocType`/`DocField`: an API user is not
	always allowed to read the schema tables, and every row already carries
	every fieldname. It also means what is checked is what will actually
	arrive.

	Sampled through the step's own filters, for the same reason: a value the
	step excludes is not a value it has to map, and reporting it is how a check
	teaches people to stop reading its output.
	"""
	try:
		rows = fetch(source, doctype, filters, 0, SAMPLE)
	except Exception as raised:
		problems.append(f"could not read {doctype} from the source: {raised}")
		return None, None

	if not rows:
		problems.append(f"{doctype} has no rows on the source matching this step")
		return None, []

	return set(rows[0]), rows


def _our_fields(doctype: str, problems: list):
	"""This site's own column names for the target, or None if it is absent."""
	if not frappe.db.exists("DocType", doctype):
		problems.append(f"{doctype} is not installed on this site")
		return None

	meta = frappe.get_meta(doctype)
	return {df.fieldname for df in meta.fields} | {
		"name", "owner", "creation", "modified", "docstatus", "naming_series",
	}
