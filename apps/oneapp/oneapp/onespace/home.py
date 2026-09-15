"""The front page of a workspace: what is waiting, what is next, what is open.

The shell's front door used to be a grid of cards called Spaces — a page you
arrived at in order to leave. Nothing on it was work; it was a directory of
doors, and the switcher in the corner is a better one. So it is gone, and One's
Home is what is behind the door instead.

Three blocks, and the rule that chose them is the same one OnePeople's own home
follows: **a landing page answers the questions somebody would otherwise have
to know where to go to ask.** Not "which spaces does this workspace have" —
which the corner answers, which is where it belongs, and which nobody actually
wonders. Rather:

    what needs me      unread notifications, newest first
    what is next       the reader's own diary, today and tomorrow
    what I had open    the files they last touched

**One call, not three.** Three endpoints is three spinners and a page that
assembles itself in front of the reader. `onehr/me.py` says the same thing
about eight, and this is the same page one level up.

**Nothing here reads.** Every block is a call into the module that already owns
that question — `notifications.feed`, `diary.agenda`, `onestorage.reading` —
each of which is whitelisted and each of which goes through the framework's own
permitted read. There is no query in this file, which is the point: a home page
is a *composition*, and the moment it has a query of its own it is a fourth
opinion about what a notification is.

**A block that cannot be read is absent, not an error.** A workspace with no
calendar sources, a site where the Drive has never been opened, an app half
through a migration — none of those is a reason for somebody's front page to be
a stack trace. Each block is tried and dropped.
"""

import frappe
from frappe.utils import add_days, nowdate

#: How many rows a block carries. Small on purpose: this is a page you glance
#: at on the way somewhere, and each block says where the rest of it is.
ROWS = 6

#: How far ahead "what is next" looks. Today and tomorrow, because a diary
#: block that shows next Thursday is a diary block nobody reads twice.
AHEAD = 1


@frappe.whitelist(methods=["GET"])
def mine() -> dict:
	"""The three blocks.

	Not who is reading them: the shell already holds the reader's own name and
	avatar — `lib/shell/user.js`, off the session payload — and a page that
	asked the server again for something it is already holding is a round trip
	spent on a greeting.
	"""
	return {
		"attention": _try(_attention),
		"day": _try(_day),
		"files": _try(_files),
	}


def _try(read):
	"""One block, or nothing at all.

	Logged rather than swallowed: a block that is quietly always empty is a
	feature nobody knows is broken, and the log is where that becomes findable.
	"""
	try:
		return read()
	except Exception:
		frappe.log_error(title="OneSpace home block failed")
		return []


def _attention() -> list[dict]:
	"""What is waiting, unread first.

	The panel's own rows, from the panel's own reader, so a notification says
	the same sentence and goes to the same place in both — and so a kind
	somebody muted is muted here too.
	"""
	from oneapp.onespace import notifications

	rows = (notifications.feed(limit=ROWS * 3) or {}).get("rows") or []
	unread = [one for one in rows if not one.get("read")]
	return (unread or rows)[:ROWS]


def _day() -> list[dict]:
	"""Today and tomorrow, out of the merged diary.

	Merged, so an interview in OnePeople and a meeting somebody typed into their
	own calendar are one list — which is the whole of what OneCalendar is for
	and the reason this does not query `Event`.
	"""
	from oneapp.onecalendar import diary

	today = nowdate()
	found = (diary.agenda(today, add_days(today, AHEAD)) or {}).get("events") or []
	return found[:ROWS]


def _files() -> list[dict]:
	"""What the reader last touched.

	The Drive's Recent place, which is a `where` on the same table as every
	other place — see `onestorage/components/places.js`. So this is the same
	list, shortened, and pressing a row lands where pressing it there would.
	"""
	from oneapp.onestorage import reading

	found = (reading.listing(place="recents", limit=ROWS) or {}).get("files") or []
	return found[:ROWS]
