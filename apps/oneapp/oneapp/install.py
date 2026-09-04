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
	"""Two things the framework does not store and this product needs.

	**`File.r2_key`** — the R2 object key. Derivable from the document, but
	storing it means a rename or a change to the key scheme cannot orphan
	objects we can no longer find to delete.

	**The mail folder pair** — `Communication.custom_imap_folder` and
	`Email Account.custom_folder_kinds`. Frappe syncs a mailbox folder by
	folder and then throws the folder away: `InboundMail` is handed it and
	nothing on the Communication records where the message was filed. So
	somebody's Applicants folder arrives as part of one flat list and their
	filing is gone. See `oneapp_core/email/folders.py`, which fills both in.

	Also on `after_migrate`, because a site installed before these existed has
	to get them too.
	"""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as make

	from oneapp.oneapp_core.email.folders import FOLDER_FIELD
	from oneapp.oneapp_core.email.threading import THREAD_FIELD

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
			],
			"Communication": [
				{
					# Which conversation a message belongs to.
					#
					# The subject with its `Re:` stripped is what mail clients
					# threaded on for twenty years, and it is wrong twice: two
					# people who both write "Invoice" are one conversation, and
					# a reply somebody renamed is a new one. This inherits the
					# parent's key through `in_reply_to` instead, so the chain
					# holds however the subject drifts — see
					# `oneapp_core/email/threading.py`.
					"fieldname": THREAD_FIELD,
					"label": "Conversation",
					"fieldtype": "Data",
					"read_only": 1,
					"no_copy": 1,
					"search_index": 1,
				},
				{
					"fieldname": FOLDER_FIELD,
					"label": "IMAP Folder",
					"fieldtype": "Data",
					"read_only": 1,
					"no_copy": 1,
					# Indexed, because it is the filter behind every folder in
					# the rail — a mail list is "this address, this folder,
					# newest first" and without the index that is a scan of the
					# whole correspondence table on every click.
					"search_index": 1,
				}
			],
			"Email Account": [
				{
					# The day an out-of-office stops. Frappe has the reply and
					# the switch and no end date, which is the part that
					# matters: one somebody forgot to turn off answers their
					# mail for a month, telling everybody they are away when
					# they are back. `rules.expire_away` acts on this daily.
					"fieldname": "custom_away_until",
					"label": "Away Until",
					"fieldtype": "Date",
					"no_copy": 1,
				},
				{
					"fieldname": "custom_folder_kinds",
					"label": "Folder Kinds",
					"fieldtype": "Small Text",
					"read_only": 1,
					"hidden": 1,
					"no_copy": 1,
				}
			],
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
