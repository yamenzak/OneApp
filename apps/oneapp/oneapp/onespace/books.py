"""Company setup — ERPNext's wizard, without the wizard.

ERPNext ships a multi-step setup wizard on the desk. The desk is not part of
this product (docs/ONEADMIN.md, No desk), so on a OneSpace workspace that wizard is never run —
which is not a cosmetic gap. Until it is, there is no Company, no Fiscal Year and
no chart of accounts, `System Settings.setup_complete` is 0, and every accounting
document fails for want of a default company. Books is installed and unusable.

So the four answers the wizard actually needs are asked here instead, and the
rest of it — presets, price lists, the chart itself — is ERPNext's own
`setup_complete`, called programmatically. Reimplementing that would be a second
copy of a hundred fixtures to keep in step with a dependency we do not control.

Everything is guarded on ERPNext being installed. A workspace entitled to no
accounting app has none of this, and the control site has no ERPNext at all.
"""

import datetime

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from oneapp.onespace import workspace
from oneapp.onespace.workspace import require_owner

# Whether the company on this site was set up from signup's answers rather than
# by a person. Kept in Frappe's own defaults store so this needs no schema of
# its own — the question is one bit and it is asked once.
ASSUMED_KEY = "oneapp_books_assumed"

# Ported from ERPNext's own setup wizard, which carries this table in
# `erpnext/public/js/setup_wizard.js` and nowhere a Python caller can reach.
# Everything absent is January to December, which is what the wizard also
# assumes. `tests/test_books_setup.py` re-reads that file when ERPNext is
# installed and fails if the two have drifted.
FISCAL_YEARS = {
	"Afghanistan": ("12-21", "12-20"),
	"Australia": ("07-01", "06-30"),
	"Bangladesh": ("07-01", "06-30"),
	"Costa Rica": ("10-01", "09-30"),
	"Egypt": ("07-01", "06-30"),
	"Ethiopia": ("07-08", "07-07"),
	"Hong Kong": ("04-01", "03-31"),
	"India": ("04-01", "03-31"),
	"Iran": ("06-23", "06-22"),
	"Kenya": ("07-01", "06-30"),
	"Malaysia": ("07-01", "06-30"),
	"Myanmar": ("04-01", "03-31"),
	"Nepal": ("07-16", "07-15"),
	"New Zealand": ("04-01", "03-31"),
	"Pakistan": ("07-01", "06-30"),
	"Singapore": ("04-01", "03-31"),
	"South Africa": ("03-01", "02-28"),
	"United Kingdom": ("04-01", "03-31"),
}


def fiscal_year_for(country: str | None) -> tuple[str, str]:
	"""The financial year a country is on, as ERPNext's wizard would offer it.

	Same algorithm: if this year's start date has not arrived yet, the current
	year is the one that began last year — otherwise a workspace created in
	February on an April-to-March year would be given a year that has not
	started.
	"""
	start_md, end_md = FISCAL_YEARS.get(country or "", ("01-01", "12-31"))
	year = getdate(nowdate()).year
	next_year = year + 1 if (start_md, end_md) != ("01-01", "12-31") else year

	if f"{year}-{start_md}" > str(getdate(nowdate())):
		next_year = year
		year -= 1

	return f"{year}-{start_md}", f"{next_year}-{end_md}"


def erpnext_installed() -> bool:
	return "erpnext" in frappe.get_installed_apps()


def _require_erpnext():
	if not erpnext_installed():
		frappe.throw(_("This workspace has no accounting app."))


@frappe.whitelist()
def status() -> dict:
	"""Whether books are set up, and what to ask if not."""
	require_owner()

	if not erpnext_installed():
		return {"available": False}

	company = frappe.get_all(
		"Company",
		fields=["name", "company_name", "abbr", "default_currency", "country"],
		limit=1,
	)
	fiscal = frappe.get_all(
		"Fiscal Year",
		fields=["name", "year_start_date", "year_end_date"],
		order_by="year_start_date desc",
		limit=1,
	)

	return {
		"available": True,
		"ready": bool(company),
		"company": company[0] if company else None,
		"fiscal_year": fiscal[0] if fiscal else None,
		# The wizard writes this, and other ERPNext code reads it to decide
		# whether the site is usable at all.
		"setup_complete": bool(frappe.db.get_single_value("System Settings", "setup_complete")),
		"defaults": _defaults(),
		# The two closed lists the form asks for. Only where there is a form to
		# ask them on: a workspace whose books are set up is shown a summary, and
		# four hundred names on it would be four hundred names nobody reads.
		#
		# Here rather than typed, for the reason `workspace.reference` gives:
		# these have to match a Frappe row exactly or ERPNext's setup throws, and
		# nothing on a text box says how the row is spelled.
		"countries": [] if company else workspace.reference("Country"),
		"currencies": [] if company else workspace.reference("Currency"),
		# Set up from signup's answers rather than by a person. Worth saying:
		# the country and currency came from what they chose, but the chart and
		# the financial year are ERPNext's defaults for that country, and only
		# the customer knows whether they are right.
		"assumed": bool(company) and frappe.db.get_default(ASSUMED_KEY) == "1",
		# The chart is only cheap to change while nothing is posted against it.
		"can_reset": bool(company) and not _has_entries(),
		"charts": _charts_for() if company else [],
	}


def _has_entries() -> bool:
	"""Anything posted to the ledger. The window for changing the chart."""
	for doctype in ("GL Entry", "Sales Invoice", "Purchase Invoice", "Payment Entry",
	                "Journal Entry"):
		if frappe.db.exists(doctype, {}):
			return True
	return False


def _defaults(country: str | None = None, currency: str | None = None,
              company_name: str | None = None) -> dict:
	"""What to prefill, from what the workspace already knows.

	The country and currency were chosen at signup; asking again invites a
	different answer, and a Company whose country disagrees with the site's is a
	support ticket about tax rules.
	"""
	country = country or frappe.db.get_single_value("System Settings", "country")
	start, end = fiscal_year_for(country)

	name = company_name or frappe.db.get_single_value("Website Settings", "app_name")

	return {
		"country": country,
		"currency": currency or frappe.db.get_single_value("System Settings", "currency"),
		"company_name": name,
		# The same abbreviation the automatic setup would have used. The panel
		# had its own one-liner for this and it was a worse one: it truncated to
		# five characters and *then* dropped what was not a letter, so "3M Corp"
		# came out "MCO" and "123 Ltd" came out "L".
		"abbr": _abbreviate(name),
		"fy_start_date": start,
		"fy_end_date": end,
	}


@frappe.whitelist()
def charts(country: str | None = None) -> list:
	"""Chart-of-accounts templates for a country."""
	require_owner()
	_require_erpnext()
	return _charts_for(country)


def _charts_for(country: str | None = None) -> list:
	"""Read from ERPNext rather than listed here: the set is per country, ships
	as JSON inside the app, and changes with it.

	Separate from the endpoint because the sync needs it and has no session to
	check a role against.
	"""
	if not erpnext_installed():
		return []

	from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import (
		get_charts_for_country,
	)

	country = country or frappe.db.get_single_value("System Settings", "country")
	return get_charts_for_country(country, with_standard=True)


@frappe.whitelist(methods=["POST"])
def create(company_name: str, abbr: str, country: str, currency: str,
           chart_of_accounts: str, fy_start_date: str, fy_end_date: str) -> dict:
	"""Set books up, on a person's answers."""
	require_owner()
	_run(company_name, abbr, country, currency, chart_of_accounts,
	     fy_start_date, fy_end_date, assumed=False)
	return status()


def _run(company_name: str, abbr: str, country: str, currency: str,
         chart_of_accounts: str, fy_start_date: str, fy_end_date: str,
         assumed: bool) -> None:
	"""Run ERPNext's own setup, once.

	`setup_complete` is ERPNext's documented programmatic entry — the same code
	path the wizard's last step takes. Called a second time it would try to
	insert fixtures that already exist, so the guard is a real one rather than
	politeness.
	"""
	_require_erpnext()

	if frappe.get_all("Company", limit=1):
		frappe.throw(_("This workspace already has a company."))

	from erpnext.setup.setup_wizard.setup_wizard import setup_complete

	args = {
		"company_name": company_name,
		"company_abbr": abbr,
		"country": country,
		"currency": currency,
		"chart_of_accounts": chart_of_accounts,
		"fy_start_date": fy_start_date,
		"fy_end_date": fy_end_date,
		# The wizard's own defaults for the rest. `language` and `timezone` are
		# already on System Settings and ERPNext reads them from there.
		"language": frappe.db.get_single_value("System Settings", "language") or "en",
		"timezone": frappe.db.get_single_value("System Settings", "time_zone"),
		"domain": "Services",
		"setup_demo": 0,
	}

	setup_complete(frappe._dict(args))
	apply_regional(country, currency, args.get("language") or "")

	# The wizard sets this from the desk; the programmatic path does not.
	# ERPNext reads it to decide whether the site is configured, so leaving it
	# unset leaves books half-installed in a way nothing here would show.
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	frappe.db.set_default(ASSUMED_KEY, "1" if assumed else "0")
	frappe.db.commit()


#: What "nobody has chosen this" looks like, per field. Blank for most of them;
#: the three formats are never blank in practice because the framework supplies
#: a fallback, so its fallback counts as unchosen too — the same shape of fix as
#: `sync.FRAMEWORKS` for the workspace's name.
UNCHOSEN = {
	"country": ("",),
	"currency": ("",),
	"time_zone": ("",),
	"language": ("", "en"),
	"date_format": ("", "yyyy-mm-dd"),
	"time_format": ("", "HH:mm:ss"),
	"number_format": ("", "#,###.##"),
}


def apply_regional(country: str, currency: str = "", language: str = "") -> dict:
	"""The half of the setup wizard ERPNext's own entry point does not run.

	`erpnext.setup_wizard.setup_complete` is three stages — fixtures, company,
	defaults — and none of them touches System Settings. Frappe's wizard runs a
	fourth, `update_global_settings`, *before* handing over to the app, and that
	is the one that writes where the workspace is: country, language, time zone,
	currency, and the date, time and number formats that follow from the
	country.

	So a workspace set up through here had books that knew they were in the
	United Arab Emirates and a Regional tab that was blank — every date in
	`yyyy-mm-dd`, every number in `#,###.##`, and no site time zone at all,
	which is the value `dayjsLocal` converts every timestamp in the product
	*from*.

	Frappe's own function is deliberately not called: it also sets
	`backup_limit`, `enable_scheduler` and `rounding_method`, and the first two
	are the platform's rather than the customer's — see
	docs/WORKSPACE-SETTINGS.md. This writes the seven that are theirs.

	Fills only what nobody has chosen, so it is safe to run again on a workspace
	set up before it existed — which is the point, because that is every
	workspace set up so far.
	"""
	if not country:
		return {}

	wanted = {
		"country": country,
		"currency": currency,
		"language": language,
		# Frappe's wizard reads this from the browser it is running in. There is
		# no browser here, so it comes from the country — `Country.time_zones`
		# is a list and the first is the one to offer, which is what the desk's
		# own country picker does with it.
		"time_zone": _zone_for(country),
		"date_format": frappe.db.get_value("Country", country, "date_format") or "",
		"time_format": frappe.db.get_value("Country", country, "time_format") or "",
		"number_format": _number_format_for(country),
	}

	filled = {}
	for field, value in wanted.items():
		if not value:
			continue
		current = frappe.db.get_single_value("System Settings", field) or ""
		# Already answered, or already this. The second half matters: a country
		# whose format *is* the framework's fallback stays "unchosen" for ever,
		# so without it every sync would report writing something it did not.
		if current not in UNCHOSEN[field] or current == value:
			continue
		frappe.db.set_single_value("System Settings", field, value)
		filled[field] = value
	return filled


def _zone_for(country: str) -> str:
	"""The first time zone a country lists, or nothing."""
	zones = (frappe.db.get_value("Country", country, "time_zones") or "").strip()
	return zones.splitlines()[0].strip() if zones else ""


def _number_format_for(country: str) -> str:
	"""How a country writes a number, corrected the way Frappe's wizard does.

	Two of the values in its country table are *currency* formats with no
	decimal places, which is wrong for a float.
	"""
	from frappe.geo.country_info import get_country_info

	number = (get_country_info(country) or {}).get("number_format") or ""
	return {"#.###": "#.###,##", "#,###": "#,###.##"}.get(number, number)


def ensure_setup(hint: dict | None) -> dict:
	"""Set books up at provisioning, from what signup already answered.

	Called by the sync, because the control plane has no route into this
	database. Books is a generally available app, so without this every new
	workspace opens it to an ERPNext error about a missing default company —
	the wizard that would have created one lives on a desk the customer never
	sees.

	What is assumed is narrow: the country and the currency are what they chose
	at signup, the company is the workspace's own name, and the chart and the
	financial year are ERPNext's defaults *for that country* — the same ones its
	wizard would have offered, which is what most people accept. `status()`
	reports that it was assumed, and OneSpace offers to start over for as long
	as nothing has been posted.
	"""
	if not erpnext_installed():
		return {"skipped": "no accounting app"}

	if existing := frappe.get_all("Company", fields=["country", "default_currency"], limit=1):
		# Set up, but possibly before `apply_regional` existed — which is every
		# workspace so far, and each one has a blank Regional tab and no site
		# time zone to show for it. Fills blanks only, so a sync running this
		# every fifteen minutes changes nothing once it has.
		return {
			"skipped": "already set up",
			"regional": apply_regional(existing[0].country, existing[0].default_currency),
		}

	hint = hint or {}
	defaults = _defaults(
		country=hint.get("country"),
		currency=hint.get("currency"),
		company_name=hint.get("company_name"),
	)

	if not (defaults["country"] and defaults["currency"] and defaults["company_name"]):
		# Guessing a country would guess a chart of accounts and a tax regime.
		# Better to leave books unset and let OneSpace ask.
		return {"skipped": "not enough known"}

	available = _charts_for(defaults["country"])
	if not available:
		return {"skipped": f"no chart of accounts for {defaults['country']}"}

	_run(
		company_name=defaults["company_name"],
		abbr=_abbreviate(defaults["company_name"]),
		country=defaults["country"],
		currency=defaults["currency"],
		chart_of_accounts=available[0],
		fy_start_date=defaults["fy_start_date"],
		fy_end_date=defaults["fy_end_date"],
		assumed=True,
	)
	return {"created": defaults["company_name"], "chart": available[0]}


def _abbreviate(name: str) -> str:
	"""ERPNext puts this on every account name, so it has to be short and safe.

	Its own wizard takes initials; a one-word name has none. ASCII only —
	`str.isalpha()` is Unicode-aware, so "Ünïcode Çø" abbreviates to "ÜÇ", which
	is a legal Python string and an unpleasant surprise in a ledger export, a
	filename or anything that builds an identifier from it. A name with no ASCII
	letters gets a placeholder the customer can change rather than a mangled
	version of itself.
	"""
	letters = [c for c in (name or "").upper() if "A" <= c <= "Z"]
	words = [w for w in (name or "").upper().split() if w]

	if len(words) > 1:
		# The first *letter* of each word, not the first character: taking the
		# character and dropping it afterwards for not being one is how "3M
		# Corp" abbreviated to "C" and "123 Ltd" to "L" — one letter, on every
		# account name in the ledger.
		initials = "".join(
			next((c for c in word if "A" <= c <= "Z"), "") for word in words
		)[:5]
	else:
		initials = "".join(letters[:5])

	# Two characters is the floor. Below it the initials say nothing — a name
	# whose words are mostly numbers gets the letters it does have instead.
	if len(initials) < 2:
		initials = "".join(letters[:3])

	return initials or "CO"


@frappe.whitelist(methods=["POST"])
def reset() -> dict:
	"""Undo an assumed setup, while that is still cheap.

	Only offered before anything is posted. A chart of accounts is structure the
	whole ledger hangs off, so after the first entry this is a migration rather
	than a button — which is exactly why the assumed setup is announced rather
	than left to be discovered.
	"""
	require_owner()
	_require_erpnext()

	if _has_entries():
		frappe.throw(
			_("This workspace has posted entries, so its chart of accounts can no "
			  "longer be replaced here. Ask support.")
		)

	for doctype in ("Account", "Cost Center", "Fiscal Year", "Price List", "Company"):
		for name in frappe.get_all(doctype, pluck="name"):
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True,
			                  ignore_on_trash=True, delete_permanently=True)

	frappe.db.set_single_value("System Settings", "setup_complete", 0)
	frappe.db.set_default(ASSUMED_KEY, "0")
	frappe.db.commit()
	return status()
