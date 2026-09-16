"""Everything with a date on it, for the person asking.

The calendar a screen offers reads one doctype. This one reads all of them: the
week you actually have is a quotation due on Tuesday, a site visit on Wednesday
and the review somebody put in your diary, and no single screen holds those
three. So this is a *merge* first — most of what is on it belongs somewhere else and
says where — and a small store second: the events that are the reader's own
have nowhere else to live, and `Event` is where the framework already puts
them.

**A calendar is a question, not a container** — `docs/WORK.md` §6. There is one
merge and two lenses over it:

* **Mine** — the entries that are about *me*: my own events, and every source
  that can say which person its rows concern. A source says that with `about`
  on its calendar declaration, which is a filter fragment in the same shape a
  screen's own filters take, so `{"employee": "@me:employee"}` is resolved by
  the same `mine.py` that narrows a twin screen. A source that cannot say is
  not personal and is left out of this lens rather than guessed at.
* **Everyone** — the whole merge, exactly as before. Who is off, which
  interviews are booked, what lands this month.

Mine is the default, because a calendar opened on a Tuesday morning is a
question about your Tuesday. Before the lens existed there was only Everyone,
which for a manager is the company's month and for everybody else was
accidentally their own.

Two sources, and both are already permissioned:

* **Every screen the reader can open that declares a calendar.** Resolved and
  filtered through the same path the screen's own calendar uses, so a record
  absent from that screen is absent here for the same reason.
* **The reader's own `Event` rows** — Frappe's core doctype, which is what a
  workspace already has for "a thing in somebody's diary". Theirs means owned
  by them or naming them as a participant: an events *screen* shows the
  workspace's, and this shows yours.

Named `diary` and not `calendar` because a module called `calendar` inside a
package is one import away from shadowing the standard library's, which is the
kind of bug that surfaces three files later.
"""

import frappe
from frappe import _

from ..onespace.spaceview import _all_filters, _resolve, _view_types, _window, visible
from ..onespace import sync


#: Where a merged entry came from, and what a click on it should do.
FROM_SCREEN = "record"
FROM_EVENT = "event"

#: The two lenses. `MINE` is the default and `EVERYONE` is the old behaviour.
MINE = "mine"
EVERYONE = "everyone"
LENSES = (MINE, EVERYONE)


#: Frappe's own. Nothing here writes one, so the shape is all we need.
EVENT = "Event"


@frappe.whitelist(methods=["GET"])
def agenda(since: str | None = None, until: str | None = None,
           lens: str = MINE) -> dict:
	"""The reader's days, merged from every calendar this workspace has.

	`since` and `until` are the days on screen, the same pair the screen-level
	calendar sends and for the same reason: a diary is not a page, and a month
	drawn from whichever rows sorted first has holes in it.

	`lens` is whose days these are — see the module docstring. An unknown value
	is `mine` rather than an error: this runs on every month somebody pages
	through, and a typo in a query string should narrow rather than break.

	Empty rather than fatal where a source cannot be read. One screen whose
	doctype was revoked between the manifest and the query is not a reason to
	take somebody's whole week away.
	"""
	lens = lens if lens in LENSES else MINE
	spaces = visible(sync.state().get("spaces") or [])
	mine = _own_events(since, until)
	found = _once(_from_screens(spaces, since, until, lens) + mine)
	_theirs(found, mine)
	# By when they start, so the merge reads as one diary rather than as its
	# sources laid end to end. The grid sorts within a day itself.
	found.sort(key=lambda one: (one.get("start") or "", one.get("title") or ""))
	return {"events": found, "sources": _sources(spaces, lens), "lens": lens}


@frappe.whitelist(methods=["GET"])
def about(space_code: str, screen: str, name: str,
          since: str | None = None, until: str | None = None) -> dict:
	"""Everything dated that is about one record — `docs/WORK.md` §6(c).

	A project's month, an employee's, a client's. **Declared nowhere**: the
	record shell already says which screens are about one of these and which
	field points back — the tabs in a manifest's showcase, and the connections
	derived from the schema beside them — so a record's calendar is that same
	list read as a calendar. A manifest that gains a tab gains a calendar with
	it, and one that never had either has nothing to draw.

	Two differences from the diary, and both follow from the question being
	about one record rather than about somebody's week.

	It does not ask for `diary`. A timesheet does not belong in everybody's
	calendar and absolutely belongs in this project's, because the reader asked
	about this project and nothing else.

	And there is no lens. "Mine" over one record would be the reader's own rows
	about a thing they opened *because* it is not only theirs; the narrowing
	here is the record.
	"""
	from oneapp.onespace.spaceview.records import record as one_record

	# The parent, by its own screen's rules, before anything else is read. A
	# record this reader cannot open is not one whose month they may have.
	resolved = _resolve(space_code, screen)
	if not resolved.get("doctype") or not one_record(
		space_code=space_code, screen=screen, name=name,
	):
		return {"events": [], "sources": []}

	space = _space(space_code)
	found, sources = [], []
	for one in _about_screens(space, resolved):
		other = _screen_named(space, one.get("screen"))
		if not other:
			continue
		narrow = [[one["field"], "=", name]]
		# A Dynamic Link needs both halves, which is what `where` carries —
		# the same pair `RelatedRows` sends.
		for pair in one.get("where") or []:
			narrow.append([pair[0], "=", pair[1]] if len(pair) == 2 else list(pair))
		try:
			rows = _screen_rows(space, other, since, until, EVERYONE, narrow, False)
		except Exception:
			frappe.log_error(title="A record's calendar could not read a screen")
			continue
		# Listed whether or not it has anything this month, for the reason the
		# diary's own rail lists every source: a row that appears and
		# disappears as somebody pages is a legend that moves under the cursor.
		sources.append({
			"key": f"{space_code}/{one['screen']}",
			"label": one.get("label") or other.get("label") or one["screen"],
			"space": space_code,
			"space_label": space.get("space_label") or space_code,
			"screen": one["screen"],
			"mine": False,
		})
		found += rows

	found = _once(found)
	found.sort(key=lambda row: (row.get("start") or "", row.get("title") or ""))
	return {"events": found, "sources": sources}


def _space(space_code: str) -> dict:
	"""One visible space by its code, or an empty one."""
	for space in visible(sync.state().get("spaces") or []):
		if space.get("space_code") == space_code:
			return space
	return {}


def _screen_named(space: dict, screen: str) -> dict:
	for one in space.get("screens") or []:
		if one.get("screen") == screen:
			return one
	return {}


def _about_screens(space: dict, resolved: dict) -> list[dict]:
	"""The screens that are about this record, declared first and derived after.

	The manifest's showcase tabs in the order it wrote them, then the
	connections the engine worked out from the schema — which is the order the
	record's own tab strip draws them in, so the calendar's rail and the tabs
	above it read alike. `resolve.connections` already leaves out a screen the
	showcase declared, so nothing is here twice.
	"""
	declared = (resolved.get("view_settings") or {}).get("showcase") or {}
	found = []
	for one in (declared.get("tabs") or []) + (resolved.get("connections") or []):
		if one.get("screen") and one.get("field"):
			found.append(one)
	return found


def _theirs(found: list[dict], mine: list[dict]) -> None:
	"""Mark the entries that are the reader's own event, screen or no screen.

	The de-duplication above hands a shared workspace's events screen the win,
	which is right for opening a *record*: the screen is where the doctype's
	own form and rules are. It is wrong for the one thing this surface writes.
	A workspace with an events screen would otherwise let somebody press New
	here, write an event, and then never be able to edit it from the diary they
	wrote it in — the entry would open the screen instead.

	So ownership is carried separately from where the entry came from. The
	surface reads it as "yours opens here", and everything else opens where it
	lives.
	"""
	owned = {one["record"] for one in mine}
	for one in found:
		one["mine"] = one.get("doctype") == EVENT and one.get("record") in owned


def _once(found: list[dict]) -> list[dict]:
	"""One entry per record, however many sources reached it.

	A workspace with an events screen puts the same meeting in front of the
	same person twice — once because it is on that screen, once because it is
	in their own diary — and a calendar that draws Tuesday's review twice is
	one nobody trusts about Wednesday.

	Screens are folded in first and win, because a screen entry can be opened:
	it knows where the record lives. The personal row knows only that the
	record exists.
	"""
	seen, kept = set(), []
	for one in found:
		at = (one.get("doctype") or "", one.get("record") or "")
		if at in seen:
			continue
		seen.add(at)
		kept.append(one)
	return kept


def _from_screens(spaces: list, since, until, lens: str = EVERYONE) -> list[dict]:
	"""Every calendar-declaring screen's records in the range."""
	found = []
	for space in spaces:
		for screen in space.get("screens") or []:
			if not _in_diary(screen):
				continue
			if lens == MINE and not _personal(screen):
				# Not "show it anyway": a source that cannot say whose a row is
				# would put the whole company's interviews in one person's
				# week, which is the thing this lens exists to stop.
				continue
			try:
				found += _screen_rows(space, screen, since, until, lens)
			except Exception:
				# A screen that cannot be read is one screen missing from the
				# merge, not an error page over the other four. Logged rather
				# than swallowed silently — this is where a revoked doctype or
				# a manifest typo shows up.
				frappe.log_error(title="Diary: a screen could not be read")
	return found


def _screen_rows(space: dict, screen: dict, since, until,
                 lens: str = EVERYONE, narrow=(), asked_for=True) -> list[dict]:
	"""One screen's records, through that screen's own resolution.

	`_resolve` rather than a query written here: the screen's filters, its
	permissions and the doctype's own User Permissions all live on that path,
	and a second way in is a second thing to keep in step.

	In the Mine lens the source's `about` is added to those filters as one more
	clause. It is not a second query path either — it is the same
	`[field, op, value]` shape the screen's own filters become, resolved by the
	same `mine.py`, so "my leave" asked here and "My leave" asked as a screen
	narrow identically and cannot come apart.
	"""
	code = space.get("space_code") or ""
	resolved = _resolve(code, screen.get("screen"), view_type="calendar")
	dates = resolved.get("calendar") or {}
	start, end = dates.get("start_field"), dates.get("end_field")
	if not resolved.get("doctype") or not start:
		return []
	if asked_for and not dates.get("diary"):
		# A calendar of its own and not a place in this one. Opt-in, because
		# "every record with a date on it" is not a diary — see `_calendar`.
		#
		# `asked_for` is false when the question is about one *record* rather
		# than about somebody's week: a project's own month wants its
		# timesheets on it whether or not they belong in everybody's diary,
		# because the reader asked about this project and nothing else.
		return []

	window = _window(resolved, since, until)
	if not window:
		# No range is not "everything": a diary asking for nothing should get
		# nothing rather than every row this screen has ever had.
		return []

	mine_only = _about_filters(dates.get("about")) if lens == MINE else []
	if lens == MINE and not mine_only and not _narrowed(screen):
		return []

	title = resolved.get("title_field") or "name"
	rows = frappe.get_list(
		resolved["doctype"],
		fields=list(dict.fromkeys(["name", title, start] + ([end] if end else []))),
		filters=(_all_filters(resolved, resolved.get("asked") or [])
		         + window + mine_only + list(narrow)),
		limit_page_length=MAX_PER_SCREEN,
	)
	return [
		{
			# Unique across the merge: two screens over two doctypes can both
			# have a record called `EV00001`.
			"id": f"{code}/{screen.get('screen')}/{row.name}",
			"title": str(row.get(title) or row.name),
			"start": str(row.get(start) or ""),
			"end": str(row.get(end) or "") if end else "",
			"kind": FROM_SCREEN,
			"doctype": resolved["doctype"],
			"space": code,
			"space_label": space.get("space_label") or code,
			"screen": screen.get("screen"),
			"screen_label": screen.get("label") or screen.get("screen"),
			"record": row.name,
		}
		for row in rows
	]


#: Per screen, per month. High enough that a real month is never truncated,
#: low enough that a screen over a busy doctype cannot make this one request
#: fetch a year of rows. A month past this is a screen to open on its own.
MAX_PER_SCREEN = 500


def _own_events(since, until) -> list[dict]:
	"""The reader's own `Event` rows.

	Theirs, not the workspace's: owned by them, or naming them among the
	participants. An events *screen* is where somebody reads what the workspace
	has; a diary is where they read what is theirs.

	Two queries and a union rather than one with an `or_filters`, because
	Frappe cannot put two OR groups in one `get_all` and the participant half
	is a join. Both go through `get_list`, so `Event`'s own permissions still
	decide.
	"""
	if not since or not until:
		return []

	me = frappe.session.user
	window = [[EVENT, "starts_on", "between", [since, until]]]
	fields = ["name", "subject", "starts_on", "ends_on"]

	mine = frappe.get_list(EVENT, fields=fields, filters=window + [[EVENT, "owner", "=", me]],
	                       limit_page_length=MAX_PER_SCREEN)
	joined = frappe.get_list(
		EVENT,
		fields=fields,
		filters=window + [
			["Event Participants", "reference_doctype", "=", "User"],
			["Event Participants", "reference_docname", "=", me],
		],
		limit_page_length=MAX_PER_SCREEN,
	)

	seen, out = set(), []
	for row in mine + joined:
		if row.name in seen:
			continue
		seen.add(row.name)
		out.append({
			"id": f"event/{row.name}",
			"title": str(row.subject or row.name),
			"start": str(row.starts_on or ""),
			"end": str(row.ends_on or ""),
			"kind": FROM_EVENT,
			"doctype": EVENT,
			"space": "",
			"space_label": "",
			"screen": "",
			"screen_label": _("Your diary"),
			"record": row.name,
		})
	return out


def _about_filters(about) -> list:
	"""The clauses that make a source's rows the reader's own, or `[]`.

	`about` is a filter fragment — `{"employee": "@me:employee"}` — and it is
	deliberately the *same* shape a screen's `filters` take, so there is one
	spelling of "this row is theirs" in the product and `mine.py` is the one
	place that resolves it. A reader the site cannot identify resolves to
	`NOBODY`, which is a value no row holds: an unidentifiable reader's
	personal calendar is empty rather than everybody's.
	"""
	if not isinstance(about, dict) or not about:
		return []

	from oneapp.onespace import mine as subjects

	found = []
	for field, value in (subjects.resolve(about) or {}).items():
		operator, wanted = ("=", value)
		if isinstance(value, (list, tuple)) and len(value) == 2:
			operator, wanted = value

		if field == ASSIGNED:
			# The one row of work every doctype already has. `_assign` is a
			# JSON list of user ids on the document, so Frappe's own "assigned
			# to me" is a `like` over it and this is the same clause — which is
			# what makes a screen with no owner field of its own still able to
			# answer "mine". `docs/WORK.md` §2: this is the one place the
			# assignment system and the calendar meet.
			found.append([ASSIGNED, "like", f"%{wanted}%"])
			continue

		if CHILD in field:
			# `Training Event Employee.employee` — a person named in a child
			# table rather than on the document. Frappe takes a four-part
			# clause for that, which is how `_own_events` already asks about
			# `Event Participants`.
			table, _, column = field.partition(CHILD)
			found.append([table, column, operator, wanted])
			continue

		found.append([field, operator, wanted])
	return found


#: The field every doctype has, holding who it is assigned to.
ASSIGNED = "_assign"

#: What separates a child table from its column in an `about` key.
CHILD = "."


def _narrowed(screen: dict) -> bool:
	"""Whether this screen is already about its reader.

	A twin — `My leave`, `My deals` — carries `@me` in its own filters, so it
	needs no `about` to be personal: it is *nothing but* personal. Read off the
	manifest rather than off the resolved screen, because by then the sentinel
	has become an id and the question cannot be asked any more.
	"""
	from oneapp.onespace import mine as subjects

	filters = screen.get("filters")
	if isinstance(filters, str):
		try:
			filters = frappe.parse_json(filters or "null")
		except (TypeError, ValueError):
			return False
	if not isinstance(filters, dict):
		return False

	for value in filters.values():
		if isinstance(value, (list, tuple)) and len(value) == 2:
			value = value[1]
		if subjects.wanted(value):
			return True
	return False


def _personal(screen: dict) -> bool:
	"""Whether a source belongs in the Mine lens at all."""
	if _narrowed(screen):
		return True
	settings = _settings(screen)
	calendar = (settings or {}).get("calendar")
	return bool(isinstance(calendar, dict) and isinstance(calendar.get("about"), dict)
	            and calendar["about"])


def _settings(screen: dict) -> dict:
	"""A screen's `view_settings`, however the manifest stored them."""
	settings = screen.get("view_settings")
	if isinstance(settings, str):
		try:
			settings = frappe.parse_json(settings or "null")
		except (TypeError, ValueError):
			return {}
	return settings if isinstance(settings, dict) else {}


def _in_diary(screen: dict) -> bool:
	"""Whether one screen's calendar belongs in the merge.

	Read off the manifest rather than off a resolved screen, because this is
	the *list* of sources and resolving twenty screens to draw a rail of them
	would be twenty resolutions for a list of labels. `_screen_rows` asks the
	resolved screen the same question before it queries anything, which is the
	answer that decides what is on the grid.
	"""
	if "calendar" not in _view_types(screen):
		return False
	calendar = _settings(screen).get("calendar")
	return bool(isinstance(calendar, dict) and calendar.get("diary"))


def _sources(spaces: list, lens: str = EVERYONE) -> list[dict]:
	"""What the merge is made of, so the surface can say and can filter.

	The reader's own row is always here, whether or not they have an event this
	month: a source that appears and disappears with its contents is a filter
	list that moves under the cursor.

	The list is the lens's own. In Mine it is the sources that can say whose a
	row is, and the rail is short; in Everyone it is all of them. A rail that
	listed sources the lens is not reading would be a row of switches that do
	nothing.
	"""
	found = [{
		"key": FROM_EVENT,
		"label": _("Your diary"),
		"space": "",
		"screen": "",
		"mine": True,
	}]
	for space in spaces:
		for screen in space.get("screens") or []:
			if not _in_diary(screen):
				continue
			personal = _personal(screen)
			if lens == MINE and not personal:
				continue
			found.append({
				"key": f"{space.get('space_code')}/{screen.get('screen')}",
				"label": screen.get("label") or screen.get("screen"),
				"space": space.get("space_code") or "",
				"space_label": space.get("space_label") or "",
				"screen": screen.get("screen"),
				# Whether this source could answer "mine" if asked. The rail
				# reads it to say why a source is missing from one lens.
				"mine": personal,
			})
	return found


# --------------------------------------------------------------------------- #
# The reader's own events, which are the one thing this surface stores.


@frappe.whitelist(methods=["POST"])
def save_event(values: str | dict) -> dict:
	"""Write one event of the reader's own — new, or one they already own.

	`ignore_permissions` behind this module's own gate, and the gate is
	ownership rather than the workspace's doctype grants. Those grants are how
	a *space* decides who may read its records; a diary is not a space, and
	"you may put something in your own week" is not a thing an admin should
	have to enable per workspace. `_mine` is the whole of it: a row you do not
	own is a row this endpoint will not fetch.
	"""
	values = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})

	subject = (values.get("subject") or "").strip()
	if not subject:
		frappe.throw(_("Give it a name."))

	starts_on = (values.get("starts_on") or "").strip()
	if not starts_on:
		frappe.throw(_("Say when it starts."))

	ends_on = (values.get("ends_on") or "").strip()
	# An end before the start is a typo every calendar makes possible and none
	# should store: the grid would draw a span running backwards.
	if ends_on and ends_on < starts_on:
		frappe.throw(_("It cannot end before it starts."))

	name = (values.get("name") or "").strip()
	doc = _mine(name) if name else frappe.new_doc(EVENT)
	doc.update({
		"subject": subject,
		"starts_on": starts_on,
		"ends_on": ends_on or None,
		"all_day": 1 if values.get("all_day") else 0,
		"description": values.get("description") or "",
		# Private, and not a choice on the form. A public Event is one the
		# whole site sees, and a diary is the last place to offer that by
		# accident — sharing an event is naming who is in it, which is the next
		# piece of this rather than a dropdown here.
		"event_type": "Private",
	})

	if name:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
def remove_event(name: str) -> dict:
	"""Delete one of the reader's own events."""
	doc = _mine(name)
	frappe.delete_doc(EVENT, doc.name, ignore_permissions=True)
	return {"ok": True, "removed": name}


@frappe.whitelist(methods=["GET"])
def event(name: str) -> dict:
	"""One of the reader's own events, to edit."""
	doc = _mine(name)
	return {
		"name": doc.name,
		"subject": doc.subject or "",
		"starts_on": str(doc.starts_on or ""),
		"ends_on": str(doc.ends_on or ""),
		"all_day": int(doc.all_day or 0),
		"description": doc.description or "",
	}


def _mine(name: str):
	"""One event this person owns, or a refusal.

	Owner and not participant: being invited to something is not permission to
	rewrite it. Reading one is `agenda`, which already includes the events
	somebody was named in.
	"""
	if not name or not frappe.db.exists(EVENT, {"name": name, "owner": frappe.session.user}):
		frappe.throw(_("That is not one of your events."), frappe.PermissionError)
	return frappe.get_doc(EVENT, name)
