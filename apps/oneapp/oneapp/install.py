"""Post-install setup for a tenant site."""

import frappe


def after_install():
	# Pull entitlements immediately so the site is usable the moment provisioning
	# finishes, rather than waiting for the first scheduled sync.
	from oneapp.oneapp_core import control_client, sync

	if control_client.is_provisioned():
		sync.sync_from_control_plane()
	frappe.db.commit()
