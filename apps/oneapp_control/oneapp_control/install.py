"""Post-install setup for the control plane."""

import frappe


def after_install():
	create_default_settings()


def create_default_settings():
	settings = frappe.get_single("OneApp Control Settings")
	if not settings.tenant_domain:
		settings.tenant_domain = "4dl.app"
	if not settings.press_api_url:
		settings.press_api_url = "https://frappecloud.com"
	settings.save(ignore_permissions=True)
	frappe.db.commit()
