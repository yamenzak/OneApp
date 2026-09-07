"""Every entitlement somebody already has is one they may see.

`offered` arrives defaulting to 0, which is right for a new row — a Restricted
space nobody has been told about must be invisible — and wrong for every row
that existed before the field did. A workspace using RUA today would find it
missing from their marketplace the moment there is one.

Only the enabled rows. A revoked row is a row somebody deliberately took away,
and `revoke` now clears both flags, so backfilling those would quietly hand
back what an operator removed.
"""

import frappe


def execute():
	frappe.db.sql(
		"""
		UPDATE `tabSpace Entitlement`
		SET offered = 1
		WHERE enabled = 1
		""")
	frappe.db.commit()
