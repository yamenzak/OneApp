"""Company setup — ERPNext's wizard, without the wizard.

ERPNext ships a multi-step setup wizard on the desk. The desk is not part of
this product (DECISIONS §7), so on a OneApp workspace that wizard is never run —
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

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from oneapp.oneapp_core.workspace import require_owner


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
	}


def _defaults() -> dict:
	"""What to prefill, from what the workspace already knows.

	The country and currency were chosen at signup and written into System
	Settings; asking again invites a different answer, and a Company whose
	country disagrees with the site's is a support ticket about tax rules.
	"""
	import datetime

	# The calendar year, which is the right guess far more often than it is
	# wrong, and the one field an accountant will correct without being asked.
	year = getdate(nowdate()).year

	return {
		"country": frappe.db.get_single_value("System Settings", "country"),
		"currency": frappe.db.get_single_value("System Settings", "currency"),
		"company_name": frappe.db.get_single_value("Website Settings", "app_name"),
		"fy_start_date": str(datetime.date(year, 1, 1)),
		"fy_end_date": str(datetime.date(year, 12, 31)),
	}


@frappe.whitelist()
def charts(country: str | None = None) -> list:
	"""Chart-of-accounts templates for a country.

	Read from ERPNext rather than listed here: the set is per country, ships as
	JSON inside the app, and changes with it.
	"""
	require_owner()
	_require_erpnext()

	from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import (
		get_charts_for_country,
	)

	country = country or frappe.db.get_single_value("System Settings", "country")
	return get_charts_for_country(country, with_standard=True)


@frappe.whitelist(methods=["POST"])
def create(company_name: str, abbr: str, country: str, currency: str,
           chart_of_accounts: str, fy_start_date: str, fy_end_date: str) -> dict:
	"""Run ERPNext's own setup, once.

	`setup_complete` is ERPNext's documented programmatic entry — the same code
	path the wizard's last step takes. Called a second time it would try to
	insert fixtures that already exist, so the guard is a real one rather than
	politeness.
	"""
	require_owner()
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

	# The wizard sets this from the desk; the programmatic path does not.
	# ERPNext reads it to decide whether the site is configured, so leaving it
	# unset leaves books half-installed in a way nothing here would show.
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	frappe.db.commit()

	return status()
