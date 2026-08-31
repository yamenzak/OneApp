"""`Plan Price` became `Catalogue Price`.

The table holds every Stripe Price something of ours has ever had, and the
machinery around it — exactly one current row per interval, the rest archived
but still billing whoever is on them — is the whole of price grandfathering.
Add-ons need the same behaviour and credit packs need half of it, so the table
is shared rather than copied twice under different names.

Runs `pre_model_sync`, for the reason `rename_to_onespace` gives: after the sync
Frappe has already created `Catalogue Price` from its JSON, and a rename then
would leave `tabPlan Price` behind holding every price we have ever minted —
which is the one thing in this system that cannot be regenerated, because Stripe
is still billing on those ids.

`parenttype` is rewritten with it. Frappe stamps the parent's doctype name on
every child row; the parent here is still `Plan`, so those rows are already
right, but a row written before the field existed would not be.
"""

import frappe


def execute():
	if frappe.db.exists("DocType", "Plan Price") and not frappe.db.exists(
		"DocType", "Catalogue Price"
	):
		frappe.rename_doc("DocType", "Plan Price", "Catalogue Price", force=True)

	if frappe.db.table_exists("Catalogue Price"):
		frappe.db.sql(
			"UPDATE `tabCatalogue Price` SET parenttype = 'Plan' "
			"WHERE parenttype IS NULL OR parenttype = '' OR parenttype = 'Plan Price'"
		)

	frappe.db.commit()
