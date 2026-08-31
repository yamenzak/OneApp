"""Where a doctype's JSON lives, said once.

Frappe's own `scrub`: lowercase, and both spaces and hyphens become
underscores. So "Add-on" is read from `add_on/add_on.json` and a directory named
any other way is one Frappe never looks in.

Four places had their own copy of this and three of them stopped at spaces, so
the first doctype with a hyphen in its name read as "does not exist" — in a
guard whose whole job is to notice that.
"""


def slug(doctype: str) -> str:
	return doctype.lower().replace(" ", "_").replace("-", "_")
