"""Post-install setup for a tenant site."""

import frappe


def after_install():
	create_custom_fields()
	install_notification_types()
	initial_sync()
	frappe.db.commit()


def install_notification_types():
	"""Our own Notification Type, the way the framework seeds its five.

	Also on `after_migrate`, because a site installed before the type existed
	has to get it too — see hooks.
	"""
	from oneapp.onespace.notifications import install_types

	install_types()


def create_custom_fields():
	"""Two things the framework does not store and this product needs.

	**`File.r2_key`** — the R2 object key. Derivable from the document, but
	storing it means a rename or a change to the key scheme cannot orphan
	objects we can no longer find to delete.

	**The four Drive columns.** A file manager needs to filter by what a file
	is, hide what was thrown away, and order by what was opened — and none of
	those is a question `File` can answer. See `onestorage.py`.

	Also on `after_migrate`, because a site installed before these existed has
	to get them too.
	"""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as make

	from oneapp.onestorage import KIND_FIELD, OPENED_FIELD, STATUS_FIELD, TRASHED_FIELD
	from oneapp.onedoc.text import SEQ_FIELD
	from oneapp.onesheet import TEMPLATE_FIELD

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
				},
				{
					# What this file is, derived from its mime type once on
					# insert. A column rather than a computation, for the
					# reason every list in this product stores its grouping
					# key: "show me the drawings" over four thousand files
					# cannot be a Python walk over a mime map.
					"fieldname": KIND_FIELD,
					"label": "Kind",
					"fieldtype": "Data",
					"read_only": 1,
					"no_copy": 1,
					"search_index": 1,
				},
				{
					# Thrown away, but not yet gone. Frappe deletes a File and
					# its object together, so without this the only undo for a
					# misplaced click is a backup.
					"fieldname": STATUS_FIELD,
					"label": "Status",
					"fieldtype": "Select",
					"options": "Active\nTrashed",
					"default": "Active",
					"read_only": 1,
					"no_copy": 1,
					"search_index": 1,
				},
				{
					"fieldname": TRASHED_FIELD,
					"label": "Trashed On",
					"fieldtype": "Datetime",
					"read_only": 1,
					"no_copy": 1,
				},
				{
					# Recents, without a row per person per file. A workspace's
					# file list does not need per-person recency badly enough
					# to pay for a doctype that grows with every open.
					"fieldname": OPENED_FIELD,
					"label": "Last Opened",
					"fieldtype": "Datetime",
					"read_only": 1,
					"no_copy": 1,
				},
				{
					# How many times this file's bytes have been written. What
					# `Doc Body.head_seq` and `Sheet Book.head_seq` are for the
					# two stores that have a row of their own — and a text file
					# has none, because its body *is* the object. So the counter
					# lives here, and `versions.py` reads the same number from
					# all three.
					"fieldname": SEQ_FIELD,
					"label": "Body Saves",
					# `Int` and not `Long Int`: a Custom Field's fieldtype list
					# is shorter than a doctype's and does not carry it. Two
					# billion saves of one file is not a number to plan for.
					"fieldtype": "Int",
					"default": "0",
					"read_only": 1,
					"no_copy": 1,
				},
				{
					# A sheet somebody starts from. On `File` and not on a
					# doctype of its own, because a template is a sheet and a
					# sheet is a File — so a workspace's templates are a folder
					# in the Drive, managed by managing files.
					"fieldname": TEMPLATE_FIELD,
					"label": "Is Template",
					"fieldtype": "Check",
					"default": "0",
				},
			],
			# A rule this workspace wrote, as against one an app shipped or one
			# the framework ships itself — Frappe has two non-standard
			# Notifications of its own on every site, and a customer's settings
			# page is not where the platform's error alerts belong. See
			# `onespace/alerts.py`.
			"Notification": [
				{
					"fieldname": "custom_onespace",
					"label": "Made in One",
					"fieldtype": "Check",
					"read_only": 1,
					"no_copy": 1,
					"search_index": 1,
				}
			],
			# A form this workspace made. Frappe ships two Web Forms on every
			# site and an app may install more, and each of those is part of
			# what that app *is* — a window that let somebody edit them would
			# be a window that breaks a site. Same field and the same argument
			# as the three around it. See `oneforms/service.py`.
			"Web Form": [
				{
					"fieldname": "custom_onespace",
					"label": "Made in One",
					"fieldtype": "Check",
					"read_only": 1,
					"no_copy": 1,
					"search_index": 1,
				},
				# And what the Look panel set, as the six settings rather than
				# as the CSS they became. Kept because a stylesheet cannot be
				# read back into a colour picker: `custom_css` is what the
				# page loads and this is what the panel reopens. See
				# `oneforms/theming.py`.
				{
					"fieldname": "custom_onespace_theme",
					"label": "One theme",
					"fieldtype": "Small Text",
					"read_only": 1,
					"no_copy": 1,
				},
				# Whether somebody who fills this in is written back to. Off
				# unless a form turns it on: an internal request filed through
				# a keyed link has already been acknowledged by the page, and a
				# second letter is noise. See `oneforms/invite.confirm`.
				{
					"fieldname": "custom_onespace_reply",
					"label": "Confirm to whoever filled it in",
					"fieldtype": "Check",
					"no_copy": 1,
				},
			],
			# Which of a child doctype's columns a repeating group asks for.
			# Not `description`, which is the help text a reader sees — that
			# was the first home and it leaked "item_name, qty, description"
			# onto the page under the label. See `oneforms/lines.py`.
			"Web Form Field": [
				{
					"fieldname": "custom_onespace_columns",
					"label": "OneSpace columns",
					"fieldtype": "Small Text",
					"read_only": 1,
					"no_copy": 1,
				}
			],
			# And the same mark on an assignment rule, for the same reason and
			# with a sharper edge: ERPNext ships none, but a workspace that
			# could edit *any* Assignment Rule on the site could edit one an
			# app relies on. See `onespace/routing.py`.
			"Assignment Rule": [
				{
					"fieldname": "custom_onespace",
					"label": "Made in One",
					"fieldtype": "Check",
					"read_only": 1,
					"no_copy": 1,
					"search_index": 1,
				}
			],
		},
		ignore_validate=True,
	)


def initial_sync():
	"""Pull entitlements immediately so the site is usable the moment provisioning
	finishes, rather than waiting for the first scheduled sync."""
	from oneapp.onespace import control_client, sync

	if control_client.is_provisioned():
		sync.sync_from_control_plane()
