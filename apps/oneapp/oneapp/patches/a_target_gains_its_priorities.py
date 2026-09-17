"""The first shape of `One Response Target` had one clock and one rule.

`docs/ONECRM.md` stage 6. It shipped with `hours` on the target and a
`when_field`/`when_value` pair to narrow by, which was a cut dressed as a
design: Frappe CRM's agreement has priorities, a resolution clock and a
condition, and only the last of those was worth refusing.

So the columns moved. `hours` became a `One Response Level` row — the default
one, since a target that promised everybody the same thing has exactly one
promise — and the field pair became a `One Response Rule`. Both old columns are
left on the table for this one run and dropped by the schema sync afterwards;
reading them by SQL rather than through the document is what makes that safe,
because the doctype in memory has not got them any more.
"""

import frappe

TARGET = "One Response Target"


def execute():
	if not frappe.db.table_exists(TARGET):
		return

	held = _held()
	if not held:
		return

	for row in held:
		doc = frappe.get_doc(TARGET, row["name"])
		changed = False

		# The promise. Only where there is none — a target somebody has already
		# given levels to is a target somebody has already thought about.
		if not doc.get("levels"):
			doc.append("levels", {
				"level": "Standard",
				"is_default": 1,
				# Four hours rather than zero for a row that somehow has none:
				# a level with no promise on it is a target that measures
				# nothing, and the shipped default is the honest guess.
				"respond_within": float(row.get("hours") or 4),
				"resolve_within": 0,
				"position": 0,
			})
			changed = True

		# And the narrowing, where the old pair said anything at all.
		field = (row.get("when_field") or "").strip()
		if field and not doc.get("applies_when"):
			doc.append("applies_when", {
				"fieldname": field,
				"operator": "is",
				"value": row.get("when_value") or "",
			})
			changed = True

		if changed:
			# `rolling` on, because it is the default of the field and the
			# thing the rewrite was for — a target carried forward with it off
			# would be a target quietly missing the feature.
			doc.rolling = 1
			doc.save(ignore_permissions=True)

	frappe.db.commit()


def _held() -> list[dict]:
	"""The old columns, by SQL.

	`frappe.get_all` would build its query from the *current* doctype, which no
	longer has `hours`, `when_field` or `when_value` on it — so it answers with
	an unknown-column error rather than with the data this patch exists to
	move. `information_schema` first, because a site created after the rewrite
	never had the columns and must not fail here.
	"""
	columns = {row[0] for row in frappe.db.sql(
		"""select column_name from information_schema.columns
		   where table_name = %s""", (f"tab{TARGET}",))}
	wanted = [one for one in ("hours", "when_field", "when_value")
	          if one in columns]
	if not wanted:
		return []
	return frappe.db.sql(
		"select name, {0} from `tab{1}`".format(", ".join(f"`{one}`" for one in wanted),
		                                        TARGET),
		as_dict=True,
	)
