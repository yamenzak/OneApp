"""An app became a Space, and the doctypes followed.

Runs `pre_model_sync`, which is the whole point: after the model sync Frappe has
already created the new doctypes from their JSON, and renaming then would leave
two tables — the old one holding every row anybody saved.
"""

import frappe

RENAMES = (
	("OneApp Saved View", "OneSpace Saved View"),
	("OneApp Site State", "OneSpace Site State"),
	("OneApp AI Settings", "OneSpace AI Settings"),
	("OneApp AI Feature Setting", "OneSpace AI Feature Setting"),
)

# Roles are named by whoever declared the space, so there is no fixed list of
# them — only a prefix. OneApp is the repository and is never product-facing,
# and a role is: it is offered by name in the alerts form and read back in
# every rule's sentence, so one left behind says the wrong word to a customer.
OLD_PREFIX = "OneApp "
NEW_PREFIX = "OneSpace "


def execute():
	for old, new in RENAMES:
		if frappe.db.exists("DocType", old) and not frappe.db.exists("DocType", new):
			frappe.rename_doc("DocType", old, new, force=True)

	for old in frappe.get_all(
		"Role", filters={"role_name": ("like", f"{OLD_PREFIX}%")}, pluck="name"
	):
		new = NEW_PREFIX + old[len(OLD_PREFIX):]
		if not frappe.db.exists("Role", new):
			frappe.rename_doc("Role", old, new, force=True)

	# The screen slug moved out of a field called `view`, which is now `screen`.
	# A column rename is not part of a doctype rename, so it is done here.
	table = "tabOneSpace Saved View"
	if frappe.db.table_exists("OneSpace Saved View"):
		columns = {c.get("Field") or c.get("column_name") for c in frappe.db.sql(
			f"DESCRIBE `{table}`", as_dict=True)}
		if "view" in columns and "screen" not in columns:
			frappe.db.sql_ddl(f"ALTER TABLE `{table}` CHANGE `view` `screen` varchar(140)")

	frappe.db.commit()
