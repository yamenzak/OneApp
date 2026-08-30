"""An app became a Space, and the doctypes followed.

Runs `pre_model_sync` — after the sync Frappe has already created the new
doctypes from their JSON, and a rename then would leave the old tables behind
holding every manifest anybody wrote.

The child tables are renamed too, and `parenttype` on their rows with them:
Frappe stores the parent's doctype name in every child row, so a parent renamed
without its children leaves the children pointing at a doctype that is gone.
"""

import frappe

RENAMES = (
	("OneApp App View", "OneSpace Space Screen"),
	("OneApp App Doctype", "OneSpace Space Doctype"),
	("OneApp App", "OneSpace Space"),
	("App Entitlement", "Space Entitlement"),
	("OneApp Control Settings", "OneSpace Control Settings"),
)

# (child doctype, its new parent's name)
CHILDREN = (
	("OneSpace Space Screen", "OneSpace Space"),
	("OneSpace Space Doctype", "OneSpace Space"),
)

# Column renames the doctype rename does not carry.
COLUMNS = (
	("OneSpace Space", "app_code", "space_code", "varchar(140)"),
	("OneSpace Space", "app_label", "space_label", "varchar(140)"),
	("OneSpace Space Screen", "view", "screen", "varchar(140)"),
	("Space Entitlement", "app_code", "space_code", "varchar(140)"),
)


def execute():
	for old, new in RENAMES:
		if frappe.db.exists("DocType", old) and not frappe.db.exists("DocType", new):
			frappe.rename_doc("DocType", old, new, force=True)

	for child, parent in CHILDREN:
		if frappe.db.table_exists(child):
			frappe.db.sql(
				f"UPDATE `tab{child}` SET parenttype = %s WHERE parenttype != %s",
				(parent, parent),
			)

	for doctype, old, new, kind in COLUMNS:
		if not frappe.db.table_exists(doctype):
			continue
		table = f"tab{doctype}"
		columns = {c.get("Field") or c.get("column_name") for c in frappe.db.sql(
			f"DESCRIBE `{table}`", as_dict=True)}
		if old in columns and new not in columns:
			frappe.db.sql_ddl(f"ALTER TABLE `{table}` CHANGE `{old}` `{new}` {kind}")

	frappe.db.commit()
