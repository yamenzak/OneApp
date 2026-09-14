"""Where a check-in has to happen, and on whose network.

Two rules, and only one of them is ours.

**Where.** HRMS already has it, which is worth saying because the obvious move
was to build it. A **Shift Location** carries a position and a `checkin_radius`;
a Shift Assignment points an employee's shift at one; `Employee Checkin` refuses
a log more than that far from it, with `CheckinRadiusExceededError`, once
`HR Settings.allow_geolocation_tracking` is on. All of that works and none of it
was reachable, for one reason: the browser never sent a position. So the work
here is not a geofence — it is making the one HRMS has usable, which is four
fields and a permission prompt.

**Whose network.** That HRMS has no notion of, and "you have to be on the office
wifi" is the other half of the same question in every workspace that asks the
first half. So it is ours, on a Custom Field on the same Shift Location — the
place and the network it has are one fact about an office, and splitting them
across two doctypes would mean assigning both to a shift separately.

**A browser cannot read an SSID.** There is no web API for it and there will not
be one, for good reasons. What is actually checkable is the address the request
arrives from, which for an office is its public egress — so "the office wifi" is
implemented, honestly, as "the network we see you coming from". A workspace on a
VPN sees the VPN's address, which is usually what they wanted anyway.

**This refuses; it does not decide who you are.** Every rule is read off the
place assigned to the person's own shift, and the person is `own.employee_of()`.
There is no argument here that can be pointed at somebody else.
"""

import ipaddress

import frappe
from frappe import _
from frappe.utils import getdate

#: What a check-in may be asked for beyond the fact of pressing the button.
#: Named because the browser is told which of them to collect, and asking for a
#: position a workspace does not want is a permission prompt nobody can explain.
PLACE = "place"
NETWORK = "network"

#: The field the network rule lives on. A Custom Field, argued for in OneHR's
#: manifest — HRMS has nothing that means this.
NETWORKS = "custom_checkin_networks"


def installed() -> bool:
	return bool(frappe.db.exists("DocType", "Shift Location"))


def tracking() -> bool:
	"""Whether this workspace asks where somebody is at all.

	HRMS's own switch, and it is global rather than per-place on purpose: with
	it on, `Employee Checkin` requires coordinates from everybody, including
	people whose shift has no location. That is their design and it is the
	honest one — a workspace either records where check-ins happen or it does
	not.
	"""
	if not frappe.db.exists("DocType", "HR Settings"):
		return False
	return bool(frappe.db.get_single_value("HR Settings", "allow_geolocation_tracking"))


def of(employee: str) -> dict | None:
	"""The place this person's shift says they check in at, today.

	Through the Shift Assignment, which is where HRMS keeps it — the same row
	`Employee Checkin` reads to decide the radius, so the sentence this page
	shows and the refusal that follows cannot disagree about which office.

	The first one where there are several. A person assigned to two places on
	one day is a workspace that has said something contradictory, and picking
	the first is what HRMS does in the same situation.
	"""
	if not employee or not installed():
		return None

	today = getdate()
	found = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": employee,
			"docstatus": 1,
			"status": "Active",
			"start_date": ["<=", today],
			"shift_location": ["is", "set"],
		},
		or_filters=[["end_date", ">=", today], ["end_date", "is", "not set"]],
		pluck="shift_location",
		limit=1,
	)
	if not found:
		return None

	place = frappe.db.get_value(
		"Shift Location", found[0],
		["name", "location_name", "latitude", "longitude", "checkin_radius", NETWORKS],
		as_dict=True,
	)
	return dict(place) if place else None


def needs(employee: str) -> dict:
	"""What a check-in by this person has to carry, and why.

	Answered before the button is drawn rather than after it is pressed, so a
	workspace that wants neither never sees a location prompt — and one that
	wants both says so where somebody can read it instead of refusing them at
	the turnstile.
	"""
	place = of(employee)
	return {
		# The radius is HRMS's to enforce and the *asking* is ours: a position
		# is only collected where the workspace has switched tracking on, which
		# is the one switch that makes `Employee Checkin` demand it.
		PLACE: bool(tracking()),
		NETWORK: bool(place and _ranges(place.get(NETWORKS))),
		"at": (place or {}).get("location_name") or "",
		"within": (place or {}).get("checkin_radius") or 0,
	}


def refuse_unless_on_network(employee: str) -> None:
	"""The one rule that is ours. Silent where a workspace has not set one.

	Raised rather than returned, and before the document is built: a check-in
	that was going to be refused should not reach HRMS's validation and become
	half a row and a rollback.
	"""
	place = of(employee)
	ranges = _ranges((place or {}).get(NETWORKS))
	if not ranges:
		return

	seen = _seen_from()
	if seen and any(seen in one for one in ranges):
		return

	frappe.throw(
		_("Check in from {0}'s own network. This one is not on the list.")
		.format(place.get("location_name") or place.get("name")),
		frappe.PermissionError,
	)


def here() -> dict:
	"""What the server can fill in without anybody typing.

	One thing: the address this request came from, which is what a manager
	sitting in the office wants written down and is the single most tedious
	value to look up. Whitelisted through `detect` below rather than here,
	because this is also read by the refusal above.
	"""
	seen = _seen_from()
	return {"address": str(seen) if seen else ""}


@frappe.whitelist(methods=["GET"])
def detect() -> dict:
	"""What the setup page cannot work out for itself: the address, and the switch.

	Two facts in one call because the page wants both at once — the address for
	the control that offers to use it, and whether this workspace records
	positions at all, because a radius with that switch off is a circle nothing
	reads and the page should say so rather than look complete.

	No permission check beyond being signed in, and none is needed: the address
	is what the caller is already sending from, and the switch is a workspace
	setting anybody in the workspace can see the effect of.
	"""
	return {**here(), "tracking": tracking()}


def _seen_from():
	"""The address this request arrived from, as something comparable.

	`request_ip` is what Frappe resolved from the connection and the proxy
	headers it trusts — reading `X-Forwarded-For` here instead would be trusting
	a header a caller sets, which is the whole of the attack on this kind of
	rule.
	"""
	raw = getattr(frappe.local, "request_ip", None)
	if not raw:
		return None
	try:
		return ipaddress.ip_address(str(raw).strip())
	except ValueError:
		return None


def _ranges(text) -> list:
	"""The declared networks, as things an address can be `in`.

	One per line. A line that is neither an address nor a range is dropped
	rather than fatal — the alternative is a typo in a settings box that stops
	everybody in the office checking in, which is a worse failure than a rule
	that is one line shorter than intended.

	A bare address is a /32 (or /128), which `ip_network` gives for free, so
	"203.0.113.7" and "203.0.113.7/32" mean the same thing and nobody has to
	know that.
	"""
	if not text:
		return []

	found = []
	for line in str(text).splitlines():
		one = line.strip()
		if not one or one.startswith("#"):
			continue
		try:
			found.append(ipaddress.ip_network(one, strict=False))
		except ValueError:
			continue
	return found
