"""A manifest-only space on the local sites, so the generic screen has
something to render.

**MockSpace**, on the rail. Two screens under it, over two of Frappe's own
doctypes rather than an invented product:

* **Tasks** (ToDo) — the field list is chosen for coverage: a Text Editor, two
  Selects (badge colours), two Links (the picker, and one that may be created
  from), a Date, and a Color, which has no frappe-ui counterpart and so must be
  shown without ever being offered. It also carries two shared saved views, so
  the sidebar has named layouts to list under it and the switcher has something
  to switch between.
* **Notes** (Note) — a second doctype under one space, which is the point: a
  space is not a doctype, and a screen is one item in its navigation.

Run it against both sites: the manifest lives on the control plane, and the
tenant caches it.

    scripts/dev.sh run scripts/seed_dev_space.py
    ONEAPP_SITE=space.localhost ONEAPP_PORT=8001 \\
      scripts/dev.sh run scripts/seed_dev_space.py

Nothing here runs on Frappe Cloud, and nothing here is a fixture the apps ship.
"""

import json
from pathlib import Path

import frappe
from frappe.utils import add_to_date, now_datetime

CODE = "zzmock"
LABEL = "MockSpace"
ROLE = "OneSpace Mock"
# Fixtures this one replaces. A dev site keeps whatever a previous fixture
# wrote, so a space that is no longer seeded stays on the rail with a role that
# still grants doctypes — a stale entitlement is a confusing thing to debug
# around and a trivial thing to clear.
RETIRED = ("zztasks",)
RETIRED_ROLES = ("OneSpace Tasks",)

# The other person on this workspace. Only the browser pass needs one, and only
# for the things that take two people: who else has a record open, and a save
# arriving from somewhere else.
COLLEAGUE = "robin@zzmock.test"
COLLEAGUE_PASSWORD = "Dev-Loop-2026!x"

TASK_FIELDS = "description,status,priority,allocated_to,role,date,color"
NOTE_FIELDS = "title,public,content"
# Event's own list fields. The child tables are not among them — a child table
# is rows rather than a value and never a column — which is the point: they are
# on the record, and only there.
EVENT_FIELDS = "subject,event_type,status,starts_on"
# No `image` here on purpose: the picture is not a column, it is what the
# record *is*. A gallery that only works where somebody remembered to list the
# image field in the manifest is a gallery that mostly does not work — the
# doctype already says which field it is, and the resolver fetches it whether
# or not anybody is looking at that column.
#
# And not the two fields the title is made of: Contact's `title_field` is
# `full_name`, so a card listing `first_name` and `last_name` under "Ada
# Sinclair" says her name three times. A caption is what the picture does not
# already say.
PEOPLE_FIELDS = "company_name,designation"

# The submittable fixture, and the one thing here that is not a Frappe doctype.
#
# Core Frappe ships exactly one submittable doctype — `DuckDB Sync` — and a
# sync job is not a thing to draw an approval on. ERPNext has a dozen and is not
# installed on a development bench. So the fixture makes one: the smallest
# document that has a docstatus and something to approve about it.
#
# It carries `workflow_state` because a workflow needs a field to keep its state
# in, and Frappe adds one automatically only through the desk's workflow
# builder, which this product does not have.
APPROVAL_DOCTYPE = "zzApproval"
APPROVAL_FIELDS = "title,amount,workflow_state"

# The workflow over it. Two of the three states carry a `doc_status`, which is
# the whole point of the fixture: approving is what *submits*, so the plain
# Submit button is never beside these.
#
# `zzVoided` is separate from `zzRejected` for a reason Frappe enforces: a
# transition may not go from a draft state straight to a cancelled one, the
# same rule the bare docstatus has. Rejecting sends it back to a draft;
# voiding is what cancels something already approved.
WORKFLOW = "zzApproval Flow"
WORKFLOW_STATES = [
	("zzDraft", "0", "Primary", ROLE),
	("zzPending", "0", "Warning", ROLE),
	("zzApproved", "1", "Success", ROLE),
	("zzRejected", "0", "Danger", ROLE),
	("zzVoided", "2", "Inverse", ROLE),
]
WORKFLOW_TRANSITIONS = [
	("zzDraft", "zzSend", "zzPending"),
	("zzPending", "zzApprove", "zzApproved"),
	("zzPending", "zzReject", "zzRejected"),
	("zzRejected", "zzSend", "zzPending"),
	("zzApproved", "zzVoid", "zzVoided"),
]

# What the space grants. ToDo and Note are what its screens show; Role is a
# link target, granted so the picker's Create row has somewhere to create —
# a link to a doctype the space did not grant is readable and never creatable,
# and both halves are worth having in the fixture.
DOCTYPES = [
	{"document_type": "ToDo", "access": "Manage", "if_owner": 0},
	{"document_type": "Note", "access": "Manage", "if_owner": 0},
	{"document_type": "Role", "access": "Manage", "if_owner": 0},
	# The child-table fixture. Frappe's Event is the one core doctype that
	# carries every question a child grid raises at once: two child tables, a
	# required column in one (`reference_doctype`), an Int column in the other
	# (`before`), and a status Select on the parent that a board can column by.
	# Inventing a doctype to ask those four questions would be inventing a
	# doctype to test our own code with.
	{"document_type": "Event", "access": "Manage", "if_owner": 0},
	# The gallery fixture. Contact is the one core doctype that declares an
	# `image_field` and a `title_field` that is not its id — which is exactly
	# what a grid needs to be a gallery rather than a page of tiles.
	{"document_type": "Contact", "access": "Manage", "if_owner": 0},
	# The docstatus fixture. `Manage` because that is the access level that
	# carries submit, cancel and amend — Read and Write do not, which is
	# itself worth having a fixture prove.
	{"document_type": APPROVAL_DOCTYPE, "access": "Manage", "if_owner": 0},
	# The two registers OneSpace ships itself, and the reason they are in this
	# fixture rather than in the customer space they came out of: they are
	# ordinary records rendered by the generic engine, so a screen over each is
	# what proves that claim on every browser run.
	{"document_type": "Compliance Document", "access": "Manage", "if_owner": 0},
	{"document_type": "Correspondence", "access": "Manage", "if_owner": 0},
]

# Enough of each register to read as one. The compliance columns are the
# question it answers — what expires, when, and whose — and the correspondence
# ones are the pair of subjects, because a bilingual register that shows only
# the English half is the register they already had.
COMPLIANCE_FIELDS = "title,category,about,expiry_date,status"
CORRESPONDENCE_FIELDS = "kind,subject,subject_ar,to_party,letter_date,status"

SCREENS = [
	{
		"screen": "tasks", "label": "Tasks", "icon": "lucide-file-text",
		# Oldest first, so the three written-out tasks lead and the forty
		# backlog rows trail them. A fixture reads better as "three real tasks
		# and a long tail" than as forty numbered ones, and it makes the first
		# row a stable thing for a browser test to point at.
		"document_type": "ToDo", "fields": TASK_FIELDS, "order_by": "creation asc",
		# More than one, so the sidebar has something to expand — and all three
		# of the built ones, because a screen offering a list, a board and a
		# grid is what the switcher, the gear and the two card layouts are
		# there for.
		"view_types": "list,board,grid,dashboard",
		# Where a task stands, which is what the badge beside its name says.
		# A fieldname and nothing else: the colours are ToDo's own.
		"status_field": "status",
		# The dashboard, declared and nothing more. Every widget here is an
		# aggregate over the rows this screen already narrows to, so there is
		# no query to write and no second permission model to keep in step —
		# see `oneapp_core/dashboard.py`.
		#
		# Six of them, and deliberately one of each family: a reading, a ring,
		# bars, a line down time, a funnel and a grid. A fixture with three bar
		# charts proves the bar chart works and nothing else.
		"view_settings": json.dumps({"dashboard": {"widgets": [
			{"kind": "number", "label": "Open", "aggregate": "count",
			 "filters": {"status": "Open"}, "width": 3},
			{"kind": "number", "label": "Closed", "aggregate": "count",
			 "filters": {"status": "Closed"}, "width": 3},
			{"kind": "donut", "label": "By status", "group_by": "status",
			 "width": 6},
			{"kind": "bar", "label": "By priority", "group_by": "priority",
			 "width": 6},
			{"kind": "line", "label": "Raised over time", "group_by": "date",
			 "grain": "month", "width": 6},
			{"kind": "heatmap", "label": "Priority against status",
			 "group_by": "priority", "series": "status", "width": 12},
		]}}),
	},
	{
		"screen": "notes", "label": "Notes", "icon": "lucide-book-open",
		"document_type": "Note", "fields": NOTE_FIELDS, "order_by": "modified desc",
	},
	{
		"screen": "events", "label": "Events", "icon": "lucide-calendar",
		"document_type": "Event", "fields": EVENT_FIELDS, "order_by": "creation asc",
		"status_field": "status",
		# The calendar fixture, and the screen it belongs on: an Event is the
		# one core doctype that is *about* a span of time. Calendar first,
		# because a list of two events sorted by creation is not how anybody
		# reads a diary.
		"view_types": "calendar,gantt,list",
		# `ends_on` is not in `EVENT_FIELDS` on purpose — the resolver fetches
		# the dates a calendar places a record by whether or not anybody made
		# them columns, and a fixture that listed them would not prove it.
		# The Gantt reads the same pair — it declares nothing of its own, which
		# is the fallback working: a screen placing its records by two dates
		# should not have to say so twice.
		"view_settings": json.dumps({
			"calendar": {"start_field": "starts_on", "end_field": "ends_on"},
		}),
	},
	{
		# Grid first, because that is what this screen is for: Contact declares
		# an image field, so its grid is a gallery and the gallery is the point
		# of opening it. The list is still there for the same records read as
		# lines.
		"screen": "people", "label": "People", "icon": "lucide-users",
		"document_type": "Contact", "fields": PEOPLE_FIELDS,
		"order_by": "first_name asc", "view_types": "grid,list",
	},
	{
		# The docstatus and workflow fixture. Every other screen here is over a
		# doctype Frappe ships; this one is over a doctype the seed makes,
		# because core Frappe has exactly one submittable doctype and it is a
		# sync job.
		"screen": "approvals", "label": "Approvals", "icon": "lucide-shield",
		"document_type": APPROVAL_DOCTYPE, "fields": APPROVAL_FIELDS,
		# And a report, because this is the screen with money on it: `amount` is
		# a Currency, so the totals row has something to add up, and an approval
		# whose figure was typed wrong is exactly the thing somebody wants to fix
		# without opening the record.
		"order_by": "creation desc", "view_types": "list,report",
		# No `status_field`, deliberately. A workflow's state *is* where the
		# record stands, and the record header already says it — pointing the
		# screen's badge at the same field makes the header say it twice in two
		# places. The list still shows the state, as an ordinary column.
	},
	{
		# The register of papers that expire. Grouped under one screen rather
		# than one per category, because "what expires next" is the question
		# and it does not care whether the answer is a visa or a licence.
		"screen": "compliance", "label": "Compliance", "icon": "lucide-shield",
		"document_type": "Compliance Document", "fields": COMPLIANCE_FIELDS,
		# Most urgent first, and by status rather than by date: `expiry_date asc`
		# puts the documents that never expire at the very top, because SQL
		# sorts a null before every date. Sorting by status instead is what the
		# register is actually for — and it works because the four statuses are
		# *named* so that their alphabetical order is their urgency order
		# (Expired, Expiring, No expiry, Valid). That is a real coupling, so
		# `test_the_statuses_sort_into_urgency` pins it rather than leaving it
		# to be discovered by whoever renames one.
		"order_by": "status asc, expiry_date asc",
		# And a tree, over the register's own renewal lineage. `renews` and
		# `renewed_by` are both Links to Compliance Document and only one of
		# them nests — which is the case that made the parent field something a
		# manifest declares rather than something the server infers.
		"view_types": "list,board,tree",
		"view_settings": '{"tree": {"parent_field": "renews"}}',
		"status_field": "status",
		"singular": "Document",
	},
	{
		# Bilingual letters and forms. Newest first: correspondence is read
		# from the top, unlike a register of dates.
		"screen": "correspondence", "label": "Correspondence",
		"icon": "lucide-mail",
		"document_type": "Correspondence", "fields": CORRESPONDENCE_FIELDS,
		"order_by": "creation desc", "view_types": "list",
		"status_field": "status",
		"singular": "Letter",
	},
]

# Shared layouts on the Tasks screen: no user, so the whole workspace sees
# them. These are what the sidebar lists under a screen alongside its view
# types, and what the switcher in the breadcrumb line switches between.
LAYOUTS = [
	# One with an icon and one without, because both render and only one of
	# them proves the fallback still says who a view is for.
	{
		"label": "Open work", "screen": "tasks", "icon": "lucide-clock",
		"filters": json.dumps([["status", "=", "Open"]]),
		"order_by": "priority asc",
	},
	{
		"label": "High priority", "screen": "tasks",
		"filters": json.dumps([["priority", "=", "High"]]),
		"order_by": "modified desc",
	},
]

# Named, not hashed. ToDo autonames by hash, so a row deleted and remade — by
# the litter sweep below, or by hand — comes back with a different id, and the
# browser tests that read an id off a row started failing on a fixture that was
# otherwise identical. A fixture's ids are part of the fixture.
TODOS = [
	# `assigned` is not a field. It is `_assign`, written below — see there for
	# why the fixture does not go through Frappe's own assignment API.
	# Two people, so a card draws a stack rather than a single face and the
	# overlap is something a browser pass can actually look at.
	{"name": "zzmock-van",
	 "description": "Book the van for Thursday", "priority": "Medium", "status": "Open",
	 "allocated_to": "Administrator", "color": "#2490EF",
	 "assigned": ["Administrator", COLLEAGUE]},
	# Assigned to nobody, and it has to stay that way: `assign.spec.js` opens
	# this one to check that a record with no assignment offers the outline of
	# a person, and assigns it itself.
	{"name": "zzmock-halloway",
	 "description": "Chase the Halloway invoice", "priority": "High", "status": "Open"},
	# Allocated to the colleague on purpose. Frappe's ToDo has a permission
	# rule of its own — owner, allocated_to, assigned_by — so a second person
	# cannot so much as join the realtime room for a task that is none of
	# those, and the row of faces has nothing to show. This is the one record
	# in the fixture two people can both be in.
	{"name": "zzmock-q3",
	 "description": "File Q3 returns", "priority": "Low", "status": "Closed",
	 "allocated_to": COLLEAGUE, "assigned": [COLLEAGUE]},
]

NOTES = [
	{"title": "Van hire terms", "public": 1,
	 "content": "<p>Collection before nine, or the day counts as two.</p>"},
	{"title": "Halloway contacts", "public": 0,
	 "content": "<p>Chris is the one who signs; Sam answers the phone.</p>"},
]

# Two events, and only one of them has rows in its child tables — a grid with
# nothing in it and a grid with three lines are different renderings and both
# are worth having something to look at.
#
# `starts_on` is a fixed date rather than "today": a fixture whose values move
# is a fixture a test cannot assert against.
def _this_month(day: int, at: str) -> str:
	"""A day in the month being looked at, rather than a date in 2026.

	The calendar opens on today's month, so a fixture pinned to a fixed date is
	a fixture that is on screen until that month passes and invisible after —
	and a browser test that reads "there is an event on the grid" would start
	failing on the first of some month with nobody having touched the calendar.
	The 10th and the 12th, because both are in every month.
	"""
	return f"{now_datetime().strftime('%Y-%m')}-{day:02d} {at}"


EVENTS = [
	{
		"subject": "Quarterly review", "event_type": "Private", "status": "Open",
		# A span: it starts at ten and ends at half eleven, which is what makes
		# the calendar draw a block rather than a dot.
		"starts_on": _this_month(10, "10:00:00"),
		"ends_on": _this_month(10, "11:30:00"),
		"event_participants": [
			{"reference_doctype": "User", "reference_docname": "Administrator",
			 "attending": "Yes"},
			{"reference_doctype": "User", "reference_docname": COLLEAGUE,
			 "attending": "Maybe"},
		],
		"notifications": [
			{"type": "Email", "before": 30, "interval": "minutes"},
			{"type": "Email", "before": 2, "interval": "hours"},
			{"type": "Email", "before": 1, "interval": "days"},
		],
	},
	{
		# And one with no end on the day it starts — a moment on the calendar,
		# and deliberately absent from the Gantt, which is a chart of lengths
		# and has nothing to draw for a record with one date.
		#
		# Somebody else's, too: the diary opens an event you own in its own
		# dialog and a record you do not on the screen it belongs to, and a
		# fixture where every event is yours can only ever show one of those.
		# `owner` is set after the insert — it is a system field.
		"subject": "Van collection", "event_type": "Public", "status": "Open",
		"starts_on": _this_month(12, "09:00:00"),
		"__owner": COLLEAGUE,
	},
	{
		# And one that runs for days rather than hours. A two-hour meeting is a
		# sliver on a chart whose column is a week, so a fixture of nothing but
		# meetings shows a Gantt that is technically right and demonstrates
		# nothing — this is the record that makes the view look like the view.
		"subject": "Fit-out week", "event_type": "Private", "status": "Open",
		"starts_on": _this_month(15, "09:00:00"),
		"ends_on": _this_month(19, "17:00:00"),
	},
]

# The gallery's records.
#
# Two have no picture, deliberately: a gallery has to say "nobody has given
# this one a picture" without collapsing the card, and that is only visible
# when some cards have one and some do not.
#
# `name` on the last one is set rather than derived, and it is the other half
# of the same idea. Contact names itself after the person, so its id and its
# title are the same string and a card has nothing to put under the name —
# which is right, and hides the case where a doctype names its records by a
# series and the card has two things to say. One of each, in one gallery.
CONTACTS = [
	{"first_name": "Ada", "last_name": "Sinclair", "company_name": "Halloway & Co",
	 "designation": "Operations", "picture": "dusk"},
	{"first_name": "Bo", "last_name": "Ferreira", "company_name": "Halloway & Co",
	 "designation": "Accounts", "picture": "moss"},
	{"first_name": "Cleo", "last_name": "Nakamura", "company_name": "Westbrook Vans",
	 "designation": "Fleet", "picture": "clay"},
	{"first_name": "Dev", "last_name": "Okonjo", "company_name": "Westbrook Vans",
	 "designation": "Scheduling"},
	{"first_name": "Esi", "last_name": "Adeyemi", "company_name": "Marlow Studio",
	 "designation": "Design", "name": "CONTACT-ZZ-0001"},
]

# The pictures, drawn rather than downloaded.
#
# A fixture that fetches photographs needs a network and inherits somebody
# else's licence; one that ships them puts binaries in a repository that has
# none. An SVG gradient is neither: a few hundred bytes of text written into
# the site's own public files, the same on every machine, and dark enough to be
# an honest test of white type over a picture — which is what the gallery card
# actually has to survive.
PICTURES = {
	"dusk": ("#1f2937", "#7c3aed"),
	"moss": ("#052e16", "#0891b2"),
	"clay": ("#431407", "#dc2626"),
}


def _write_pictures():
	"""The fixture's pictures, in the site's public files. Returns their paths."""
	folder = Path(frappe.get_site_path("public", "files"))
	folder.mkdir(parents=True, exist_ok=True)

	paths = {}
	for key, (dark, bright) in PICTURES.items():
		svg = (
			'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">'
			f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
			f'<stop offset="0" stop-color="{bright}"/>'
			f'<stop offset="1" stop-color="{dark}"/>'
			"</linearGradient></defs>"
			'<rect width="400" height="400" fill="url(#g)"/>'
			f'<circle cx="300" cy="120" r="70" fill="{bright}" fill-opacity="0.35"/>'
			f'<circle cx="110" cy="300" r="130" fill="{dark}" fill-opacity="0.45"/>'
			"</svg>"
		)
		name = f"zzmock-{key}.svg"
		(folder / name).write_text(svg)
		paths[key] = f"/files/{name}"
	return paths

# The paging fixture. Everything else here is two or three records, which is
# right for reading a screen and useless for testing what happens at the end of
# a page — Load More, the count, the windowing threshold. Closed, so it does
# not crowd the Open work layout.
BACKLOG = 40
BACKLOG_PREFIX = "Backlog item"

# Field metadata the UI honours and stock Frappe never sets. These are
# ERPNext-shaped flags — a doctype there marks the two or three fields worth
# seeing on hover, the one worth reading heavy, and how wide a column wants to
# be — and nothing on a plain bench declares one, so there is nothing to look
# at unless the fixture says so.
PROPERTIES = [
	("User", "email", "in_preview", 1, "Check"),
	("User", "enabled", "in_preview", 1, "Check"),
	("User", "user_type", "in_preview", 1, "Check"),
	("ToDo", "priority", "bold", 1, "Check"),
	("ToDo", "description", "columns", 4, "Int"),
	# The doctype's own rules, so a browser pass exercises the whole chain:
	# the field is hidden until the task is closed, and required once it is.
	# `sender` and not `role`: a rule on a field another test drives is a rule
	# that breaks it, and the link tests type into Role.
	#
	# `hidden` first, and it is not decoration. ToDo ships `sender` hidden, and
	# a hidden field is not offered at all — `depends_on` decides whether a
	# field somebody can see is showing, not whether a field nobody can see
	# becomes visible. So a rule on a hidden field is a rule on nothing, and
	# this fixture was asserting against a control that was never rendered.
	("ToDo", "sender", "hidden", 0, "Check"),
	("ToDo", "sender", "depends_on", 'eval:doc.status=="Closed"', "Data"),
	("ToDo", "sender", "mandatory_depends_on", 'eval:doc.status=="Closed"', "Data"),
	# And one that goes the other way: the reference is settled while the task
	# is open and stops being editable once it is closed.
	("ToDo", "reference_type", "read_only_depends_on", 'eval:doc.status=="Closed"', "Data"),
]


# The two registers, with rows that read as real ones. Dates are relative to
# the day the seed runs, so the register always has something expired, something
# about to be and something fine — which is the only way to look at a screen
# whose whole job is to sort by urgency.
COMPLIANCE = [
	# Three years of one licence, so the register has a shape and not just a
	# length: `renews` points each at the one it replaced, which is what the
	# tree view nests by. The same document number all the way down, because
	# that is what renewing a licence does to it.
	("Trade Licence — 2024", "Licence", "CN-1109482", -377, 60,
	 "Department of Economic Development", "Abu Dhabi"),
	("Trade Licence", "Licence", "CN-1109482", -12, 60,
	 "Department of Economic Development", "Abu Dhabi"),
	("Trade Licence — 2027", "Licence", "CN-1109482", 353, 60,
	 "Department of Economic Development", "Abu Dhabi"),
	("Residence Visa — Ali Haddad", "Visa", "784-1990-2237841-6", 9, 60,
	 "ICP", "Abu Dhabi"),
	("Vehicle Registration — 14/52931", "Registration", "52931", 26, 30,
	 "Abu Dhabi Police", "Abu Dhabi"),
	("Workmen Compensation Policy", "Insurance", "WC-2026-04417", 121, 45,
	 "Oman Insurance", "Dubai"),
	("Chamber of Commerce Certificate", "Certificate", "ADCCI-77210", 240, 30,
	 "ADCCI", "Abu Dhabi"),
	# The one with no date, because "does not expire" has to be visibly a
	# different thing from "expired".
	("Memorandum of Association", "Contract", "MOA-2019-01", None, 30,
	 "Notary Public", "Abu Dhabi"),
]

# Which of them replaced which, by title: `renews` holds an id, and a fixture
# written in ids would be a fixture nobody can read. Applied after the inserts
# rather than during, because the older document has to exist first — and
# through `save` rather than `db.set_value`, so the doctype's own rule writes
# `renewed_by` back on the other side of the pair.
RENEWALS = [
	("Trade Licence", "Trade Licence — 2024"),
	("Trade Licence — 2027", "Trade Licence"),
]

# Bilingual on purpose: this fixture is what proves `dir="auto"` puts an Arabic
# subject to the right of its box and an English one to the left, in the same
# list, without either being declared anywhere.
CORRESPONDENCE = [
	("Letter", "Request for extension of completion date",
	 "طلب تمديد تاريخ الإنجاز", "Al-Ittihad Consultants", "الاتحاد للاستشارات",
	 "Issued"),
	("Letter", "Submission of revised shop drawings",
	 "تقديم مخططات التنفيذ المعدلة", "National Engineering Bureau",
	 "المكتب الوطني للهندسة", "Issued"),
	("Form", "Material approval — 6mm tempered glass",
	 "اعتماد مواد — زجاج مقسى ٦ ملم", "A.D.D. Consultants",
	 "إيه دي دي للاستشارات", "Draft"),
]


def _seed_registers():
	"""A few rows in each register, so the screens are worth opening."""
	from frappe.utils import add_days, nowdate

	for title, category, number, offset, warn, issuer, place in COMPLIANCE:
		if frappe.db.exists("Compliance Document", {"title": title}):
			continue
		frappe.get_doc({
			"doctype": "Compliance Document",
			"title": title, "category": category, "document_number": number,
			"expiry_date": add_days(nowdate(), offset) if offset is not None else None,
			"issue_date": add_days(nowdate(), (offset or 0) - 365),
			"remind_days": warn, "issued_by": issuer, "place_of_issue": place,
		}).insert(ignore_permissions=True)

	for title, renews in RENEWALS:
		found = frappe.db.get_value("Compliance Document", {"title": title}, "name")
		older = frappe.db.get_value("Compliance Document", {"title": renews}, "name")
		if not (found and older):
			continue
		one = frappe.get_doc("Compliance Document", found)
		if one.renews == older:
			continue
		one.renews = older
		one.save(ignore_permissions=True)

	for kind, subject, subject_ar, to, to_ar, status in CORRESPONDENCE:
		if frappe.db.exists("Correspondence", {"subject": subject}):
			continue
		frappe.get_doc({
			"doctype": "Correspondence",
			"naming_series": "LTR-.YY.-" if kind == "Letter" else "FRM-.YY.-",
			"kind": kind, "subject": subject, "subject_ar": subject_ar,
			"to_party": to, "to_party_ar": to_ar, "status": status,
			"letter_date": nowdate(),
			"body": "<p>Further to our meeting on site, we write to confirm…</p>",
			"body_ar": "<p>إلحاقاً باجتماعنا في الموقع، نود أن نؤكد…</p>",
			"signed_by": "Yamen Zakhour", "signed_by_title": "Managing Director",
			"signed_by_ar": "يامن زخور", "signed_by_title_ar": "المدير العام",
		}).insert(ignore_permissions=True)

	frappe.db.commit()


def _seed_rua():
	"""The RUA space on the dev tenant, from the module that ships it.

	Read out of `oneapp_control.spaces.rua` rather than restated here: there is
	one declaration of what that space is, and a fixture that kept its own copy
	would drift from it inside a week.

	Only where ERPNext is installed. Every screen but two is over an ERPNext or
	HRMS doctype, and a space whose screens are all skipped is a rail item that
	opens onto nothing.
	"""
	from oneapp.oneapp_core import sync
	from oneapp_control.spaces import rua

	if not frappe.db.exists("DocType", "Sales Invoice"):
		return None

	sync.ensure_role(rua.SPACE["role_name"])

	me = frappe.get_doc("User", "Administrator")
	if rua.SPACE["role_name"] not in {one.role for one in me.roles}:
		me.append("roles", {"role": rua.SPACE["role_name"]})
		me.save(ignore_permissions=True)

	# The grants go back to the caller rather than being written here.
	# `sync_permissions` *reconciles*: it removes what is not in the list it is
	# given, so two calls leave whichever ran last and silently take the other
	# space's permissions away — which is a space on the rail that redirects to
	# the sign-in page, and reads like a session bug.
	return (
		{**rua.SPACE, "screens": [dict(one, component=None) for one in rua.SCREENS]},
		[{"role": rua.SPACE["role_name"], "doctype": document_type,
		  "access": access, "if_owner": if_owner}
		 for document_type, access, if_owner in rua.DOCTYPES],
	)


def _seed_mail(user):
	"""An address this person holds, and one conversation on it.

	Two messages with the same subject and a `Re:` in front of the second,
	because that is the whole of what threading is here and a fixture with one
	message proves nothing about it.

	`enable_incoming` is off and there is no server: an address in this product
	is a delivery point, not a mailbox, and mail arrives by the Worker POSTing
	it. A fixture that set an IMAP host would have Frappe try to reach one.
	"""
	from oneapp.oneapp_core.email import addresses

	# The workspace's own domain, asked for rather than spelled out: a fixture
	# that hard-coded `4dl.app` would seed an address the product then badges
	# as somebody else's domain, and the panel would be lying about the one
	# address it has.
	address = f"sales@{addresses.domain()}"
	if not frappe.db.exists("Email Account", {"email_id": address}):
		frappe.get_doc({
			"doctype": "Email Account",
			"email_account_name": address,
			"email_id": address,
			"enable_incoming": 0,
			"enable_outgoing": 0,
			"signature": "Sales — MockSpace",
			"add_signature": 1,
		}).insert(ignore_permissions=True)

	account = frappe.db.get_value("Email Account", {"email_id": address}, "name")
	holder = frappe.get_doc("User", user)
	if address not in {row.email_id for row in holder.user_emails}:
		holder.append("user_emails", {"email_account": account, "email_id": address})
		holder.save(ignore_permissions=True)

	# The folders a connected mailbox would have brought with it, and the kinds
	# the server would have flagged. Written here rather than discovered,
	# because discovering them needs an IMAP server and what this fixture is
	# for is the rail that draws them.
	from oneapp.oneapp_core.email import folders as folder_lib

	mirrored = [
		{"name": "INBOX", "kind": "inbox"},
		{"name": "Applicants", "kind": ""},
		{"name": "Documents", "kind": ""},
		{"name": "Sent Items", "kind": "sent"},
		{"name": "Junk", "kind": "junk"},
	]
	doc = frappe.get_doc("Email Account", account)
	folder_lib.apply(doc, mirrored)
	doc.db_set(
		"custom_folder_kinds",
		frappe.as_json({one["name"]: one["kind"] for one in mirrored}),
		update_modified=False,
	)
	doc.save(ignore_permissions=True)

	# Filing rules and the away message are state a person sets, so the fixture
	# owns them the way it owns the folders: cleared, not merged. A spec that
	# adds a rule and asserts the count would otherwise pass once and fail on
	# every run after it, which reads as a broken feature rather than as a
	# fixture that remembers.
	for name in frappe.get_all("Mail Rule", pluck="name"):
		frappe.delete_doc("Mail Rule", name, force=True, ignore_permissions=True)
	doc.db_set("enable_auto_reply", 0, update_modified=False)
	doc.db_set("auto_reply_message", "", update_modified=False)
	doc.db_set("custom_away_until", None, update_modified=False)

	# A second recipient on the conversation, so a reply-to-all has somebody to
	# copy. Without one the fixture cannot tell "no Cc because the code is
	# wrong" from "no Cc because there was nobody else on it".
	both = f"{address}, ops@client.test"

	# The last number is how many hours ago it arrived, and it is not decoration:
	# a thread is ordered by `communication_date`, and four rows inserted in the
	# same millisecond leave that order to the database. The reader now collapses
	# what has been read and marks where the new mail starts, both of which are
	# statements about *which message is last* — so the fixture says.
	messages = [
		("Quotation for the Al Reem tower", "INBOX", "Received",
		 "<p>Could you send the revised cladding quote before Thursday?</p>", both, 26, ""),
		# The one with a Cc, because the reader draws one and nothing here had
		# one to draw: `cc` has always been fetched and was never rendered, so
		# who else saw a message was a question the screen could not answer.
		("Re: Quotation for the Al Reem tower", "INBOX", "Received",
		 "<p>Attached — the glazing line moved, everything else holds.</p>", both, 25,
		 "qs@alreem-consultants.ae"),
		# One in a folder somebody made, which is the whole point of mirroring
		# them, and one in Sent — stored as Sent rather than Received, which is
		# what `OneSpaceInboundMail` does to a message out of a Sent folder.
		# With a remote image in it, which is what a tracking pixel is: the
		# host is `.invalid`, reserved by RFC 2606 so it can never resolve, and
		# the spec watches for the request rather than for a reply.
		("Fabricator — CV and trade test", "Applicants", "Received",
		 "<p>Six years on curtain wall, available from the 12th.</p>"
		 '<img src="https://tracker.invalid/open.gif" width="1" height="1">', address, 30, ""),
		("Al Reem — revised elevations", "Sent Items", "Sent",
		 "<p>Revised sheets attached, superseding revision B.</p>", "hala@client.test", 20, ""),
	]
	# A Contact for the person who writes in, so the sender chip has a face and
	# a firm to show rather than only initials — which is the difference the
	# whole of `people.py` exists to make, and a fixture without one proves
	# nothing about it.
	# Filled in rather than only created. Frappe makes a Contact of its own the
	# first time mail arrives from an address, with a first name and nothing
	# else — so a fixture that skipped when one existed would leave the thin
	# auto-made row in place and prove nothing about a resolved sender.
	person = frappe.db.get_value("Contact", {"email_id": "hala@client.test"}, "name")
	contact = frappe.get_doc("Contact", person) if person else frappe.new_doc("Contact")
	contact.update({
		"first_name": "Hala",
		"last_name": "Nasser",
		"email_id": "hala@client.test",
		"company_name": "Al Reem Consultants",
		"designation": "Project Manager",
		"mobile_no": "+971 50 000 0000",
	})
	if not any(row.email_id == "hala@client.test" for row in contact.email_ids or []):
		contact.append("email_ids", {"email_id": "hala@client.test", "is_primary": 1})
	contact.save(ignore_permissions=True)

	_sweep_mail({subject for subject, *_ in messages})

	for subject, folder, direction, content, recipients, hours, copied in messages:
		arrived = add_to_date(now_datetime(), hours=-hours)
		existing = frappe.db.get_value("Communication", {"subject": subject}, "name")
		if existing:
			frappe.db.set_value(
				"Communication", existing, "communication_date", arrived, update_modified=False
			)
			# Recipients too, for the same reason the folder is reset: a fixture
			# row written by an older version of this file is a row that no
			# longer says what the specs read off it.
			frappe.db.set_value(
				"Communication", existing, "recipients", recipients, update_modified=False
			)
			frappe.db.set_value(
				"Communication", existing, "cc", copied, update_modified=False
			)
			# Put the folder back. The fixture is what a browser pass starts
			# from, and that pass *files* things — a seed that only inserted
			# would leave every conversation wherever the last run dropped it,
			# and the next run would fail on a count nobody changed.
			frappe.db.set_value(
				"Communication", existing, folder_lib.FOLDER_FIELD, folder,
				update_modified=False,
			)
			continue
		frappe.get_doc({
			"doctype": "Communication",
			"communication_type": "Communication",
			"communication_medium": "Email",
			"sent_or_received": direction,
			"subject": subject,
			"content": content,
			"sender": address if direction == "Sent" else "hala@client.test",
			"sender_full_name": "Sales" if direction == "Sent" else "Hala Nasser",
			"recipients": recipients,
			"cc": copied,
			"email_account": account,
			"communication_date": arrived,
			folder_lib.FOLDER_FIELD: folder,
		}).insert(ignore_permissions=True)

	_seed_attachment()
	_seed_template()
	_seed_read_state(user)
	return address


def _sweep_mail(fixture: set):
	"""Everything in the mailbox that is not this fixture's four messages.

	The same litter the ToDo sweep above exists for, one doctype over and never
	swept: every browser pass sends mail, and none of it was ever removed. Sixty
	runs later the Sent folder held sixty "Cladding schedule" rows, all newer
	than the fixture's own, and the spec that asks whether Sent contains the
	fixture's message failed — not because Sent was broken but because the
	message had been pushed off the first page by the specs that ran before it.

	It also removes the *duplicates* of the fixture's own subjects. Those came
	from the same place: the insert below skips when a row with that subject
	exists, so a run that found none inserted one, and three sat side by side
	being grouped into one thread that quietly held three copies of everything.

	Every message on a dev site is this fixture's or a test's, which is the same
	assumption the ToDo sweep already makes.
	"""
	seen = set()
	for row in frappe.get_all(
		"Communication", fields=["name", "subject"], order_by="creation asc"
	):
		if row.subject in fixture and row.subject not in seen:
			seen.add(row.subject)
			continue
		frappe.delete_doc("Communication", row.name, ignore_permissions=True, force=True)


#: What the attached message is called, so a spec can name it. The *reply* —
#: it is the one whose body says "Attached", and it is the one the reader leaves
#: open, the earlier message in the thread being already read.
ATTACHED = "Re: Quotation for the Al Reem tower"
ATTACHMENT = "Al Reem cladding schedule.txt"


def _seed_attachment():
	"""A real file on a real message.

	There were none. Every mail fixture was body text — one of them says
	"Attached — the glazing line moved" and had nothing attached — so the
	reader's attachment list rendered zero rows on every run, and the code that
	drew them was never once exercised by the browser pass. It was a bare
	anchor with no size and no preview for exactly as long as that was true.

	A `.txt` and not a PDF: the Drive's previewer reads text inline, so this
	fixture proves the whole path — chip, size, click, preview with content —
	without a binary in the repository.
	"""
	message = frappe.db.get_value("Communication", {"subject": ATTACHED}, "name")
	if not message:
		return

	# Off any message but this one. The file used to hang on the first message
	# in the thread, which the reader now collapses — so it was attached to the
	# one row nobody can see. Moving it in the fixture without clearing the old
	# one would leave two.
	for stale in frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Communication", "file_name": ATTACHMENT},
		pluck="name",
	):
		doc = frappe.get_doc("File", stale)
		if doc.attached_to_name == message:
			return
		doc.delete(ignore_permissions=True)

	frappe.get_doc({
		"doctype": "File",
		"file_name": ATTACHMENT,
		"attached_to_doctype": "Communication",
		"attached_to_name": message,
		"is_private": 1,
		"content": (
			"Al Reem tower — cladding schedule\n"
			"=================================\n\n"
			"Zone 3 glazing line moved 400mm east. Everything else holds.\n"
		),
	}).insert(ignore_permissions=True)


#: The template the composer offers, so the picker has something in it.
TEMPLATE = "Delivery update"


def _seed_template():
	"""One message written once and sent often.

	The picker only appears where there is something to pick, so a fixture
	without a template is a fixture where that button does not exist — and the
	browser pass would be checking that an absent control is absent.
	"""
	from oneapp.oneapp_core.email.templates import MARK

	# Sweep first, for the reason the mailbox sweep exists: a browser pass writes
	# one to prove the settings panel writes one, and sixty runs later the picker
	# is a list of timestamps. Only ours — the six ERPNext and HRMS ship are not
	# this fixture's to delete.
	for stale in frappe.get_all("Email Template", filters={MARK: 1}, pluck="name"):
		if stale != TEMPLATE:
			frappe.delete_doc("Email Template", stale, force=True, ignore_permissions=True)

	if frappe.db.exists("Email Template", TEMPLATE):
		return

	doc = frappe.new_doc("Email Template")
	doc.update({
		"subject": "Your order is on its way",
		"response": (
			"<p>Good morning,</p>"
			"<p>The order left us this morning and is with the courier.</p>"
		),
		"use_html": 0,
		MARK: 1,
	})
	doc.name = TEMPLATE
	doc.insert(ignore_permissions=True)


def _seed_read_state(user):
	"""What this person has already read: the first message and nothing else.

	Read state is a user default, so it survived every previous browser pass —
	the fixture said nothing about it and each run inherited whatever the last
	one had opened. That was harmless while the reader drew every message the
	same way. It is not now: a read message collapses to a row and a line marks
	where the new mail begins, so "which of these have I read" decides what the
	screen looks like, and a fixture that leaves it to history is a fixture that
	makes the same test pass and fail on alternate runs.

	One read message out of a thread of two, deliberately: it is the only shape
	that shows both halves at once — something collapsed above, and a marker
	saying the rest is new.
	"""
	from oneapp.oneapp_core.email.mailbox.flags import SEEN_KEY

	first = frappe.db.get_value(
		"Communication", {"subject": "Quotation for the Al Reem tower"}, "name"
	)
	frappe.defaults.set_user_default(SEEN_KEY, first or "", user)


def _seed_import():
	"""A source and a plan, so the import console has something to render.

	Fictional on purpose: the address is a name nobody owns and the secret is a
	placeholder, so nothing here can reach anything. What it exercises is the
	panel — the card, the steps in their declared order, the watermark reading
	"not yet" before a first run, and the three buttons in the order they are
	meant to be pressed in.

	A real one lives in the app (`oneapp_core/plans/`) and is installed against
	a customer's own credentials; this is the dev site's stand-in for it.
	"""
	SOURCE = "The old system"

	if not frappe.db.exists("Import Source", SOURCE):
		frappe.get_doc({
			"doctype": "Import Source",
			"source_name": SOURCE,
			"base_url": "https://old.example.com",
			"api_key": "not-a-real-key",
			"api_secret": "not-a-real-secret",
		}).insert(ignore_permissions=True)

	PLAN = "Everything, from the old system"

	if not frappe.db.exists("Import Plan", PLAN):
		frappe.get_doc({
			"doctype": "Import Plan",
			"plan_name": PLAN,
			"source": SOURCE,
			"space_code": CODE,
			"steps": [
				{
					"source_doctype": "Old Party",
					"target_doctype": "Contact",
					"field_map": json.dumps({"first_name": {"from": "party"}}),
				},
				{
					"source_doctype": "Old Job",
					"target_doctype": "ToDo",
					# Second on purpose: a link resolved against a step that
					# runs later finds nothing on every row, and the order of
					# these rows is the order the run walks them in.
					"field_map": json.dumps({
						"description": {"from": "title"},
						"reference_name": {"from": "party", "link": "Old Party"},
					}),
				},
			],
		}).insert(ignore_permissions=True)

	frappe.db.commit()


def _seed_approvals():
	"""The submittable doctype, its workflow, and three records to move.

	Made rather than borrowed, and made on the tenant only: it is a fixture for
	the record header, and the control plane's own screens have no docstatus
	between them.

	Idempotent in the way a dev fixture has to be — the doctype is left alone if
	it is there, and the workflow is replaced outright, because a workflow's
	states and transitions are child tables and merging two versions of one by
	hand is how a fixture starts lying about what it set up.
	"""
	if not frappe.db.exists("DocType", APPROVAL_DOCTYPE):
		frappe.get_doc({
			"doctype": "DocType", "name": APPROVAL_DOCTYPE, "module": "Core",
			"custom": 1, "is_submittable": 1, "autoname": "ZZA-.#####",
			"title_field": "title", "track_changes": 1, "allow_rename": 0,
			"fields": [
				{"fieldname": "title", "fieldtype": "Data", "label": "Title",
				 "reqd": 1, "in_list_view": 1},
				{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount",
				 "in_list_view": 1},
				# A workflow keeps its state in a field on the document, and
				# `read_only` because the workflow writes it — a Select somebody
				# can set by hand is a way around every transition rule there is.
				{"fieldname": "workflow_state", "fieldtype": "Link",
				 "options": "Workflow State", "label": "State",
				 "read_only": 1, "no_copy": 1, "in_list_view": 1},
			],
			"permissions": [{
				"role": "System Manager", "read": 1, "write": 1, "create": 1,
				"delete": 1, "submit": 1, "cancel": 1, "amend": 1,
			}],
		}).insert(ignore_permissions=True)

	for state, _status, style, _role in WORKFLOW_STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({
				"doctype": "Workflow State", "workflow_state_name": state,
				"style": style,
			}).insert(ignore_permissions=True)

	for _state, action, _next in WORKFLOW_TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({
				"doctype": "Workflow Action Master", "workflow_action_name": action,
			}).insert(ignore_permissions=True)

	if frappe.db.exists("Workflow", WORKFLOW):
		frappe.delete_doc("Workflow", WORKFLOW, force=True, ignore_permissions=True)
	frappe.get_doc({
		"doctype": "Workflow", "workflow_name": WORKFLOW,
		"document_type": APPROVAL_DOCTYPE, "is_active": 1,
		"workflow_state_field": "workflow_state",
		"states": [
			{"state": state, "doc_status": status, "allow_edit": role}
			for state, status, _style, role in WORKFLOW_STATES
		],
		"transitions": [
			{
				"state": state, "action": action, "next_state": next_state,
				"allowed": ROLE,
				# A dev fixture has one person in it, so self-approval has to be
				# allowed or nothing can be moved at all. On a real workflow this
				# is the flag that stops somebody approving their own invoice.
				"allow_self_approval": 1,
			}
			for state, action, next_state in WORKFLOW_TRANSITIONS
		],
	}).insert(ignore_permissions=True)

	made = 0
	for title, amount in (("Office chairs", 1200), ("Server renewal", 4800),
	                      ("Team offsite", 2600)):
		if frappe.db.exists(APPROVAL_DOCTYPE, {"title": title}):
			continue
		frappe.get_doc({
			"doctype": APPROVAL_DOCTYPE, "title": title, "amount": amount,
		}).insert(ignore_permissions=True)
		made += 1

	# The cache keyed on doctype, which `get_workflow_name` reads. Without this
	# the workflow is invisible until the next process starts.
	frappe.clear_cache()
	return made


def seed_control():
	"""The manifest itself. Only the control plane has OneSpace Space."""
	for code in (CODE, *RETIRED):
		if frappe.db.exists("OneSpace Space", code):
			frappe.delete_doc("OneSpace Space", code, force=True, ignore_permissions=True)

	doc = frappe.get_doc({
		"doctype": "OneSpace Space", "space_code": CODE, "space_label": LABEL,
		"module": "Mock", "role_name": ROLE, "icon": "lucide-briefcase",
		"is_active": 1, "availability": "General", "sort_order": 5,
		"description": "Two screens over two doctypes, for looking at.",
	})
	for grant in DOCTYPES:
		doc.append("doctypes", grant)
	for screen in SCREENS:
		doc.append("screens", screen)
	doc.insert(ignore_permissions=True)
	print(f"control plane: {CODE} with {len(SCREENS)} screens")


def seed_tenant(manifest_only=False):
	"""The tenant's cached copy, plus records to look at.

	A dev site is not linked to a control plane, so the cache is written here
	directly — the same shape `sync_from_control_plane` would have written.

	`manifest_only` writes the first half and stops. The two halves are not an
	arbitrary split: the first is *what a space is* — its screens, its theme,
	the doctypes its role may touch — and the second is *what is in it*, plus
	the sweeps that put a fixture back the way a browser pass found it.

	Editing a manifest is the loop this exists for, and it is the loop that was
	paying for the other half. A screen declaration, a `view_settings`, a theme
	— none of them can be looked at without the cache being rewritten, and none
	of them care whether the fixture has thirteen ToDos or fourteen. Records
	are created idempotently and swept only after something has dirtied them,
	so skipping both is not a shortcut past correctness: it is not doing work
	whose answer has not changed.

	Run the whole thing before a browser pass; run this while iterating.
	"""
	from oneapp.oneapp_core import sync

	approvals = 0
	mailbox = ""
	if not manifest_only:
		# Before the manifest is cached: the screen names a doctype, and a
		# screen over a doctype the site does not have is skipped rather than
		# fatal — so seeding in the other order leaves an Approvals item that
		# quietly is not there. In `manifest_only` the doctype is already
		# there from the last full run, which is the assumption the whole mode
		# rests on.
		approvals = _seed_approvals()
		_seed_registers()
		_seed_import()
		mailbox = _seed_mail(frappe.session.user)

	state = frappe.get_single("OneSpace Site State")
	spaces = [
		one for one in json.loads(state.spaces_json or "[]")
		if one.get("space_code") not in (CODE, *RETIRED)
	]
	spaces = [one for one in spaces if one.get("space_code") != "rua"]
	rua, rua_grants = _seed_rua() or (None, [])
	if rua:
		spaces.append(rua)

	spaces.append({
		"space_code": CODE, "space_label": LABEL, "module": "Mock",
		"role_name": ROLE, "icon": "lucide-briefcase", "sort_order": 5,
		"description": "Two screens over two doctypes, for looking at.",
		"screens": [dict(v, component=None) for v in SCREENS],
	})
	state.db_set("spaces_json", json.dumps(spaces), update_modified=False)
	sync.invalidate()

	# The role, its permissions, and this session in it. On a real tenant the
	# control plane's permission sync does all three; a dev site has no control
	# plane, and a space whose role holds no DocPerms is refused at the first
	# read with "ToDo is not part of MockSpace" — which reads like a manifest
	# bug and is a fixture that stopped halfway.
	sync.ensure_role(ROLE)
	# `document_type` is the manifest child row's fieldname; `doctype` is what
	# the permission sync reads. They are not the same word, and a row with the
	# wrong one is silently skipped — which surfaces later as "ToDo is not part
	# of MockSpace" and reads like a manifest bug.
	sync.sync_permissions([
		{"role": ROLE, "doctype": grant["document_type"],
		 "access": grant["access"], "if_owner": grant["if_owner"]}
		for grant in DOCTYPES
	] + rua_grants)
	user = frappe.get_doc("User", frappe.session.user)
	if ROLE not in {r.role for r in user.roles}:
		user.append("roles", {"role": ROLE})
		user.save(ignore_permissions=True)

	# A second person on the workspace, because some things only exist between
	# two of them. Frappe's own realtime will not tell you that you are looking
	# at a record — "dont send update to self", says the handler — so a fixture
	# with one user cannot show the row of faces at all.
	if not frappe.db.exists("User", COLLEAGUE):
		frappe.get_doc({
			"doctype": "User", "email": COLLEAGUE, "first_name": "Robin",
			"last_name": "Vale", "send_welcome_email": 0, "user_type": "System User",
			"new_password": COLLEAGUE_PASSWORD,
		}).insert(ignore_permissions=True)
	colleague = frappe.get_doc("User", COLLEAGUE)
	if ROLE not in {r.role for r in colleague.roles}:
		colleague.append("roles", {"role": ROLE})
		colleague.save(ignore_permissions=True)

	if manifest_only:
		# The same last-call-wins reason the full run ends with one: everything
		# above reads the site state, and any one of those reads repopulates
		# the cache from a document this process had already loaded.
		sync.invalidate()
		print(f"tenant: {CODE} and rua re-declared — manifest, roles and permissions only")
		return

	for role in RETIRED_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		for perm in frappe.get_all("Custom DocPerm", filters={"role": role}, pluck="name"):
			frappe.delete_doc("Custom DocPerm", perm, force=True, ignore_permissions=True)
		# The people who hold it, first. `force` skips the link check, so
		# deleting the Role alone leaves a `Has Role` row pointing at nothing —
		# and the next thing to save that User fails on it. Which is not a
		# theoretical failure: installing ERPNext saves Administrator, and it
		# died here with "Could not find Row #30: Role: OneSpace Tasks".
		for held in frappe.get_all("Has Role", filters={"role": role}, pluck="name"):
			frappe.delete_doc("Has Role", held, force=True, ignore_permissions=True)
		frappe.delete_doc("Role", role, force=True, ignore_permissions=True)

	for doctype, fieldname, prop, value, prop_type in PROPERTIES:
		frappe.make_property_setter({
			"doctype": doctype, "fieldname": fieldname, "property": prop,
			"value": value, "property_type": prop_type,
		}, is_system_generated=False)

	# And take back the ones this file used to declare. A property setter
	# outlives the line that made it, so moving a rule from one field to
	# another leaves the old rule in place — which is how a `depends_on` moved
	# off `role` and went on hiding it anyway, breaking two tests that type
	# into it. Scoped to the doctypes this fixture touches and to setters it
	# made itself: a system-generated one is Frappe's own business.
	declared = {(row[0], row[1], row[2]) for row in PROPERTIES}
	for stale in frappe.get_all(
		"Property Setter",
		filters={"doc_type": ["in", sorted({row[0] for row in PROPERTIES})],
		         "is_system_generated": 0},
		fields=["name", "doc_type", "field_name", "property"],
	):
		if (stale["doc_type"], stale["field_name"], stale["property"]) not in declared:
			frappe.delete_doc("Property Setter", stale["name"], ignore_permissions=True)

	for row in TODOS:
		# Keyed on the name, which is the record's identity and is stable.
		#
		# This used to look the task up by its description, and that quietly
		# littered: ToDo sanitises a Text Editor field, so what comes back is
		# `<p>Book the van…</p>` and never matches the plain string being
		# searched for. Every run therefore decided the fixture was missing and
		# inserted another one. The realtime test then clicked whichever of the
		# duplicates sorted first — sometimes the stray, which is allocated to
		# nobody and so cannot be opened by the second user — and failed on
		# litter the seed itself had left.
		if frappe.db.exists("ToDo", row["name"]):
			# Who a task is allocated to is worth re-asserting: it decides who
			# may open it at all — Frappe's ToDo has its own permission rule —
			# and a browser pass that reassigns one would otherwise leave the
			# next run with a record its second user cannot see.
			frappe.db.set_value(
				"ToDo", row["name"], "allocated_to", row.get("allocated_to") or None
			)
		else:
			# `set_name`, not a `name` key: ToDo autonames by hash, and
			# `set_new_name` overwrites whatever is on the document unless the
			# insert was told the name is already decided.
			fields = {k: v for k, v in row.items() if k not in ("name", "assigned")}
			frappe.get_doc({"doctype": "ToDo", **fields}).insert(
				ignore_permissions=True, set_name=row["name"]
			)

		# Who it is assigned to, written straight onto the document.
		#
		# Frappe's `assign_to.add` writes this *and* inserts a ToDo beside it as
		# its bookkeeping — and the records on this screen are ToDos, so a
		# fixture assigning through the API would put its own bookkeeping in the
		# list it is a fixture for. The sweep at the end of this file would then
		# delete those rows and leave `_assign` exactly as it is here, so this
		# is the same end state reached directly rather than a shortcut past
		# one. `update_modified` off because the age on a card is part of what a
		# browser pass looks at.
		frappe.db.set_value(
			"ToDo", row["name"], "_assign",
			json.dumps(row.get("assigned") or []), update_modified=False,
		)

		# And take back any other copy of the same task — a hash-named one from
		# before these were named, or one of the duplicates the description
		# lookup produced. Matched on the text with and without the wrapper,
		# because that is exactly the difference that caused them.
		for stray in frappe.get_all(
			"ToDo",
			filters={
				"name": ["!=", row["name"]],
				"description": ["in", (row["description"], f"<p>{row['description']}</p>")],
			},
			pluck="name",
		):
			frappe.delete_doc("ToDo", stray, ignore_permissions=True, force=True)

	for row in NOTES:
		if frappe.db.exists("Note", {"title": row["title"]}):
			continue
		frappe.get_doc({"doctype": "Note", **row}).insert(ignore_permissions=True)

	for row in EVENTS:
		row, owner = {k: v for k, v in row.items() if k != "__owner"}, row.get("__owner")
		found = frappe.db.exists("Event", {"subject": row["subject"]})
		if found:
			# The dates and nothing else. These move with the month — the
			# calendar opens on today's and a fixture pinned to whenever it was
			# first seeded is one that drifts off the grid — and a site seeded
			# in a previous month would otherwise keep the old ones forever,
			# because "it exists" used to be the end of it.
			doc = frappe.get_doc("Event", found)
			doc.starts_on = row["starts_on"]
			doc.ends_on = row.get("ends_on")
			doc.save(ignore_permissions=True)
			if owner:
				frappe.db.set_value("Event", found, "owner", owner)
			continue
		made = frappe.get_doc({"doctype": "Event", **row})
		made.insert(ignore_permissions=True)
		if owner:
			frappe.db.set_value("Event", made.name, "owner", owner)

	pictures = _write_pictures()
	for row in CONTACTS:
		# Matched on the person rather than on the id, because Contact names
		# itself from the person — and one of these is named by hand instead.
		if frappe.db.exists(
			"Contact", {"first_name": row["first_name"], "last_name": row["last_name"]}
		):
			continue
		fields = {k: v for k, v in row.items() if k not in ("name", "picture")}
		if row.get("picture"):
			fields["image"] = pictures[row["picture"]]
		frappe.get_doc({"doctype": "Contact", **fields}).insert(
			ignore_permissions=True, set_name=row.get("name")
		)

	for n in range(1, BACKLOG + 1):
		description = f"{BACKLOG_PREFIX} {n:02d}"
		if frappe.db.exists("ToDo", {"description": description}):
			continue
		frappe.get_doc({
			"doctype": "ToDo", "description": description, "status": "Closed",
			"priority": ["High", "Medium", "Low"][n % 3],
		}).insert(ignore_permissions=True)

	# And their views. A browser pass that makes a view and fails before
	# deleting it leaves one behind, and three runs later "Only the urgent"
	# matches three rows and every test that names one is ambiguous. The
	# fixture's own views are the ones in LAYOUTS; anything else on this space
	# is litter.
	#
	# The unnamed ones go too, and they used to be spared. An unnamed row is a
	# person's own working state for a screen — the filters and columns they
	# have changed but not saved — so leaving one behind means the next run
	# starts with somebody else's unsaved changes, and "Save this screen" is
	# still offered on a screen nobody has touched. That is a test inheriting a
	# fixture rather than reading one.
	strays = frappe.get_all(
		"OneSpace Saved View",
		filters={"space_code": CODE, "label": ["not in", [row["label"] for row in LAYOUTS]]},
		fields=["name", "label"],
	)
	for stray in strays:
		frappe.delete_doc("OneSpace Saved View", stray["name"], ignore_permissions=True)

	# Nobody is hiding anything on a fresh fixture either — a hidden view is
	# invisible, which is the worst thing for a test to inherit.
	frappe.db.delete("OneSpace Hidden View", {"space_code": CODE})

	# And the records they make. A pass that creates one to prove creating
	# works has no reason to keep it, and forty runs later the fixture is forty
	# rows longer than it was written to be. Everything a test makes is named
	# with this prefix on purpose.
	for doctype, field in (("ToDo", "description"), ("Note", "title"),
	                       ("Event", "subject")):
		for row in frappe.get_all(doctype, filters={field: ["like", "ZZ %"]}, pluck="name"):
			frappe.delete_doc(doctype, row, ignore_permissions=True, force=True)

	# And anything else that is not this fixture.
	#
	# The prefix above only catches what a test remembered to prefix, and a run
	# that fails halfway leaves its row behind whatever it was called. Sixty of
	# those later the first page of the list is litter, the fixture's own rows
	# are on page two, and a test that creates a row and looks for it fails
	# with "100 of 105" — which reads as a bug in the list rather than as a
	# dirty fixture. Every ToDo on a dev site is this fixture's, which is the
	# same thing the comment sweep below already assumes.
	keep = {row["name"] for row in TODOS} | {
		f"{BACKLOG_PREFIX} {n:02d}" for n in range(1, BACKLOG + 1)
	}
	for row in frappe.get_all("ToDo", fields=["name", "description"]):
		if row["name"] in keep or row["description"] in keep:
			continue
		frappe.delete_doc("ToDo", row["name"], ignore_permissions=True, force=True)

	# The browser passes leave their comments behind, and Frappe keeps only the
	# last hundred of them on the document itself — which is where the count in
	# the timeline tab comes from, here as in the desk. A fixture that has been
	# commented on two hundred times therefore has a count that no longer
	# moves, and a test that adds one and watches the number goes red for a
	# reason that has nothing to do with what it tests. Every ToDo and Note on
	# a dev site is this fixture's, so this is the fixture sweeping up after
	# itself.
	for doctype in ("ToDo", "Note"):
		names = frappe.get_all(doctype, pluck="name")
		if not names:
			continue
		frappe.db.delete("Comment", {"reference_doctype": doctype, "reference_name": ("in", names)})
		# Written the way Frappe writes it: `_comments` sits beside the document
		# as a cache, and refreshing it must not move `modified`.
		frappe.db.sql(f"update `tab{doctype}` set `_comments` = '[]'")

	# And the hearts, for the same reason one step further on. Several specs
	# press one and press it again to put it back; a run that fails between the
	# two leaves the record favourited, and the next run's first attempt then
	# looks for "Add to favourites" on a control that now says "Remove from
	# favourites". It fails, retries, and the retry passes because the retry
	# toggled it — which reads as flakiness and is bookkeeping. Ten of those in
	# one pass is what sent me looking.
	#
	# `_liked_by` is a cache column beside the document like `_comments`, so it
	# is written the same way and must not move `modified` either.
	for doctype in ("ToDo", "Note", "Event", "Contact"):
		if frappe.db.exists("DocType", doctype):
			frappe.db.sql(f"update `tab{doctype}` set `_liked_by` = NULL")

	for layout in LAYOUTS:
		where = {"space_code": CODE, "screen": layout["screen"], "label": layout["label"]}
		found = frappe.db.exists("OneSpace Saved View", where)
		if found:
			# The icon is the one thing worth re-asserting: a browser test that
			# picks one leaves it behind, and the next run should look like the
			# fixture rather than like whatever the last test did.
			frappe.db.set_value("OneSpace Saved View", found, "icon", layout.get("icon", ""))
			continue
		frappe.get_doc({
			"doctype": "OneSpace Saved View", "space_code": CODE,
			# No user: shared with the whole workspace, which is what makes it
			# something the sidebar can list for anybody.
			"user": "", **layout,
		}).insert(ignore_permissions=True)

	# Again, and last. Everything between the first call and here reads the
	# site state — the permission sync does, the role grant does — and any one
	# of them repopulates the cache from a document this process had already
	# loaded. Clearing it at the end is the only order that leaves the next
	# request reading what was just written.
	sync.invalidate()

	print(
		f"tenant: {CODE} cached — {len(TODOS)} todos, {len(NOTES)} notes, "
		f"{BACKLOG} backlog rows, {len(LAYOUTS)} shared views, "
		f"{approvals} approvals under {WORKFLOW}, "
		f"a conversation on {mailbox}, "
		f"and {COLLEAGUE} to share them with"
	)


if __name__ == "__main__":
	import sys

	# `--manifest` is the iteration loop: re-declare the space and stop, which
	# is everything a screen, a `view_settings` or a theme edit needs and about
	# a tenth of the work. The full run is what a browser pass wants, because
	# only the full run sweeps up after the last one.
	manifest_only = "--manifest" in sys.argv[1:]

	# Which site this is, by what it has: only the control plane defines the
	# manifest doctype, and only a tenant has the cached copy.
	if frappe.db.exists("DocType", "OneSpace Space"):
		# The control plane *is* the manifest, so there is no half of it to
		# skip and the flag is simply not its business.
		seed_control()
	elif frappe.db.exists("DocType", "OneSpace Site State"):
		seed_tenant(manifest_only=manifest_only)
	else:
		raise SystemExit("neither a control-plane nor a tenant site")
