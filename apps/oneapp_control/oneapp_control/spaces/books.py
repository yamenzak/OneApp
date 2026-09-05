"""A reference entitlement, not a product.

Nobody has decided to build a books app. This exists so the entitlement
pipeline has something running through it end to end — registry row, sync
payload, role created with desk access off, DocPerms written from the manifest,
launcher rendering, reconciliation on removal. With an empty catalogue every one
of those paths is dead code on a fresh control plane, and a break in any of them
would go unnoticed until the first real customer.

**Restricted**, deliberately. General availability would put it in every
customer's launcher, where it points at nothing and grants write on eight
ERPNext doctypes over the REST API — a promise of software that does not exist,
made to somebody paying. An operator grants it to a workspace to exercise the
pipeline, and nobody else sees it.

Its doctype list is deliberately small. The transitive set ERPNext actually
touches on submit is not something that can be enumerated by reading, and
guessing it produces a workspace that works in a demo and breaks on the fifth
invoice. It grows from running the real flows — see docs/ONESPACE.md, Roles.
"""

SPACE = {
	"space_code": "books",
	"space_label": "Books",
	"module": "Books",
	"role_name": "OneSpace Books",
	# Eight ERPNext doctypes and nothing else. Nobody has built the interface,
	# but the entitlement is real and so is what it assumes of the site.
	"requires_apps": "erpnext",
	"icon": "lucide-book-open",
	"sort_order": 10,
	"availability": "Restricted",
	"description": (
		"Reference entitlement — no interface yet. Grant it to exercise the "
		"pipeline, not to give a customer accounting."
	),
}

DOCTYPES = [
	("Customer", "Write", 0),
	("Supplier", "Write", 0),
	("Item", "Write", 0),
	("Sales Invoice", "Manage", 0),
	("Purchase Invoice", "Manage", 0),
	("Payment Entry", "Manage", 0),
	("Address", "Write", 0),
	("Contact", "Write", 0),
]

# None. That is the point of it.
SCREENS = []
