"""Post-install setup for a tenant site."""

import frappe


def after_install():
	create_custom_fields()
	setup_outgoing_email()
	install_notification_types()
	initial_sync()
	frappe.db.commit()


def install_notification_types():
	"""Our own Notification Type, the way the framework seeds its five.

	Also on `after_migrate`, because a site installed before the type existed
	has to get it too — see hooks.
	"""
	from oneapp.oneapp_core.notifications import install_types

	install_types()


def create_custom_fields():
	"""Track the R2 object key alongside each File.

	Derivable from the document, but storing it means a rename or a change to the
	key scheme cannot orphan objects we can no longer find to delete.
	"""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as make

	make(
		{
			"File": [
				{
					"fieldname": "r2_key",
					"label": "R2 Key",
					"fieldtype": "Data",
					"read_only": 1,
					"hidden": 1,
					"no_copy": 1,
				}
			]
		},
		ignore_validate=True,
	)


def setup_outgoing_email():
	"""Point Frappe's Email Queue at Cloudflare's SMTP endpoint.

	No-ops when the token is absent, so a site without mail configured installs
	cleanly rather than failing.
	"""
	from oneapp.oneapp_core.email import outbound

	outbound.ensure_email_account()


def initial_sync():
	"""Pull entitlements immediately so the site is usable the moment provisioning
	finishes, rather than waiting for the first scheduled sync."""
	from oneapp.oneapp_core import control_client, sync

	if control_client.is_provisioned():
		sync.sync_from_control_plane()
