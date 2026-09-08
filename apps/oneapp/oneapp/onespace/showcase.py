"""How a screen draws *one* record, when a form is the wrong shape for it.

Most records are a form: fields in sections, and the sections are the doctype's
own. Some are not. A project is a photograph of a building, a contract value, a
percentage done, thirteen variation orders hanging off it and five hundred
documents filed against it — and rendering that as a column of labelled inputs
is technically a record page and practically a filing cabinet.

So a screen may declare a **showcase**: an image that fills the top of the page,
the two or three numbers somebody actually opens the record to read, the records
that hang off this one, and the other screens in the same space that point back
at it. Declared, not coded — a manifest says it and every space gets it, which
is the difference between building one customer a bespoke page and building the
thing that makes bespoke pages.

    "view_settings": {"showcase": {
      "images": true,
      "eyebrow_field": "custom_location",
      "facts": [{"field": "estimated_costing", "label": "Contract"}],
      "children": {"screen": "projects", "field": "custom_parent_project",
                   "label": "Variations"},
      "tabs": [{"screen": "invoices", "field": "project", "label": "Invoices"}]
    }}

**This is not the security boundary and does not pretend to be one.** A tab
names another screen in the same space and the field on it that points back
here; the browser then asks `rows` for that screen with that filter, and `rows`
is where the space, the permissions and the filter are all checked — the same
checks any other list goes through. What this module does is drop what is
structurally not a showcase, so a manifest with a typo renders a form rather
than a broken page.
"""

# Enough facts to read at a glance and no more. Past four it is a table, and
# the person wanting the fifth number wants the Details tab.
FACTS = 4

# Related screens. More than six tabs is a menu, and a menu of records is what
# the rail already is.
TABS = 6


def shape(asked, offered: set) -> dict:
	"""One screen's showcase, or nothing.

	Nothing rather than a partial one: half a hero — a title with no image and
	no numbers — is worse than the form it replaced, because it looks like the
	page failed rather than like a page nobody asked for.
	"""
	if not isinstance(asked, dict):
		return {}

	kept = {}

	if asked.get("images"):
		kept["images"] = True

	for key in ("eyebrow_field", "badge_field", "blurb_field"):
		value = asked.get(key)
		if isinstance(value, str) and value in offered:
			kept[key] = value

	facts = _facts(asked.get("facts"), offered)
	if facts:
		kept["facts"] = facts

	children = _related(asked.get("children"))
	if children:
		kept["children"] = children

	tabs = [one for one in (_related(raw) for raw in (asked.get("tabs") or []))
	        if one][:TABS]
	if tabs:
		kept["tabs"] = tabs

	return kept


def _facts(raw, offered: set) -> list[dict]:
	"""The numbers worth reading before anything else.

	Each is a field this screen already offers — the same rule every other
	fieldname in the settings blob goes through, because a fact reaches a query
	the same way a sort does.
	"""
	if not isinstance(raw, list):
		return []

	kept = []
	for one in raw[:FACTS]:
		if not isinstance(one, dict):
			continue
		field = one.get("field")
		if not isinstance(field, str) or field not in offered:
			continue
		label = one.get("label")
		kept.append({
			"field": field,
			"label": label if isinstance(label, str) and label else "",
		})
	return kept


def _related(raw) -> dict:
	"""Another screen in this space, and the field on it that points back.

	Structural only. Whether that screen exists, whether this person may open
	it and whether the field is one of its columns are all answered by `rows`
	when the browser asks it — and answering them twice, here, from a different
	place, is how two answers start to disagree.
	"""
	if not isinstance(raw, dict):
		return {}

	screen = raw.get("screen")
	field = raw.get("field")
	if not (isinstance(screen, str) and screen and isinstance(field, str) and field):
		return {}

	found = {"screen": screen, "field": field}
	for key in ("label", "icon"):
		value = raw.get(key)
		if isinstance(value, str) and value:
			found[key] = value
	return found
