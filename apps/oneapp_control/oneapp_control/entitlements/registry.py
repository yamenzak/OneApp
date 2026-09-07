"""Which apps a tenant may see.

Two independent axes, deliberately:

* **Plan** decides quotas — storage, seats, credits. Never which apps.
* **Entitlement** decides apps. That is what makes a single-tenant bespoke
  solution possible without inventing a plan for one customer.

An app marked General is available to everyone. An app marked Restricted appears
only where an explicit Space Entitlement exists. A Restricted app that nobody has
been entitled to is simply invisible, not an error.

An entitlement carries two independent flags, because a marketplace needs three
states and not two:

* `enabled` — they have it. It is in their launcher, and its app is on the site.
* `offered` — they may *see* it. A Restricted space with this flag appears in
  their marketplace as something they can turn on themselves; without it the
  space does not exist as far as that workspace is concerned.

Both off is a revoked row, kept for the history. Offered without enabled is the
operator lever this document calls "expose it to that customer" — and it is the
reason invisibility is the default: a marketplace that draws a locked card for
every Restricted space tells every customer the name of every bespoke solution
built for every other one.
"""

import frappe


# What describes a space to a site. One list, two readers — the tenant sync and
# the local provider — so the two cannot drift into describing different things.
SPACE_FIELDS = (
	"name as space_code", "space_label", "module", "role_name", "icon",
	"logo", "sort_order", "description", "theme", "requires_apps",
	"custom_fields",
)

# The same list as SQL, derived rather than restated. The restricted half of
# `spaces_for_tenant` is a join and cannot use `get_all`, and for a while it was
# a hand-written column list beside this one — which is a drift waiting to
# happen: a field added above and forgotten below reaches every General space
# and no Restricted one, and the Restricted ones are the bespoke work.
SPACE_COLUMNS = ", ".join(
	f"a.{field.split(' as ')[0]} AS {field.split(' as ')[-1]}" if " as " in field
	else f"a.{field}"
	for field in SPACE_FIELDS
)

# What every site has whatever it was granted. `frappe` because there is no
# site without it, `oneapp` because it is the product.
BASE_APPS = ("frappe", "oneapp")


def spaces_for_tenant(tenant: str) -> list[dict]:
	"""The manifest OneSpace renders: every space this workspace may open."""
	general = frappe.get_all(
		"OneSpace Space",
		filters={"is_active": 1, "availability": "General"},
		fields=list(SPACE_FIELDS),
	)

	restricted = frappe.db.sql(
		f"""
		SELECT {SPACE_COLUMNS}
		FROM `tabOneSpace Space` a
		INNER JOIN `tabSpace Entitlement` e ON e.app = a.name
		WHERE a.is_active = 1
		  AND a.availability = 'Restricted'
		  AND e.tenant = %(tenant)s
		  AND e.enabled = 1
		""",
		{"tenant": tenant},
		as_dict=True,
	)

	spaces = general + restricted
	spaces.sort(key=lambda s: (s.get("sort_order") or 0, s.get("space_label") or ""))

	# The screens each space puts in front of a customer — its navigation. Sent
	# with the space rather than fetched per space: OneSpace renders its sidebar
	# from this the moment a workspace opens, and a second round trip for a list
	# of four labels is a spinner where a sidebar should be.
	for space in spaces:
		space["screens"] = screens_for(space["space_code"])

	return spaces


# Every field a Space Screen carries, sent verbatim. Listed rather than `["*"]`
# so a field added here is a deliberate act — and read off the doctype in
# `tests/test_owner_and_manifest.py`, because the failure mode of a forgotten
# one is silent: `status_field` was stored, edited in the console, and never
# sent, so no screen anywhere ever showed a status badge and nothing said why.
SCREEN_FIELDS = (
	"screen", "label", "singular", "icon", "document_type", "fields", "component",
	"filters", "order_by", "view_types", "view_settings", "status_field",
	"hide_new", "tab_icons", "naming_series", "print_formats",
)


def screens_for(space_code: str) -> list[dict]:
	return frappe.get_all(
		"OneSpace Space Screen",
		filters={"parent": space_code, "parenttype": "OneSpace Space"},
		fields=list(SCREEN_FIELDS),
		order_by="idx asc",
	)


def local_spaces() -> list[dict]:
	"""Every space this site offers itself, for `oneapp` running on it.

	The control plane holds the space registry and has no control plane to ask,
	so where a tenant syncs, this reads the same rows in process. Registered
	through `onespace_space_providers` in hooks, which is `oneapp`'s one seam
	for it.

	No entitlement join, unlike `spaces_for_tenant`: there is no tenant here.
	Who sees which space is decided by role — `visible_spaces` filters on
	`role_name`, so an operator space and a customer's account space separate
	cleanly on one site — and by `_space`, which refuses a space code whose
	role the caller does not hold.
	"""
	spaces = frappe.get_all(
		"OneSpace Space",
		filters={"is_active": 1},
		fields=list(SPACE_FIELDS),
	)
	spaces.sort(key=lambda s: (s.get("sort_order") or 0, s.get("space_label") or ""))
	for space in spaces:
		space["screens"] = screens_for(space["space_code"])
	return spaces


def forget_spaces(doc=None, method=None) -> None:
	"""Drop OneSpace's cached view of this site's spaces.

	Only meaningful where `oneapp` is installed alongside this app — the
	control site. Elsewhere the import fails and there is nothing to forget,
	which is not an error: a tenant's cache is invalidated by its own sync.
	"""
	try:
		from oneapp.oneapp_core import sync
	except ImportError:
		return
	sync.invalidate()


def entitled_modules(tenant: str) -> list[str]:
	return [s["module"] for s in spaces_for_tenant(tenant) if s.get("module")]


def entitled_roles(tenant: str) -> list[str]:
	"""Roles the tenant site should hold.

	Enforcement is native Frappe permissions: each app's doctypes carry
	permissions for its role, and the tenant site adds or removes that role from
	its users on every sync. That covers desk, REST, reports and any future
	surface, which a bespoke permission hook would not.
	"""
	return sorted({row["role"] for row in permission_manifest(tenant)})


# --------------------------------------------------------------------------- #
# Role keys, and the Frappe roles they become
#
# A *key* is what a membership stores and what a manifest row names:
# `crm:sales` for a role a space ships, `custom:<label>` for one the workspace
# built. A *Frappe role* is what the tenant site actually holds — the thing
# DocPerms hang off.
#
# The Frappe name is derived rather than stored, so nothing has to be kept in
# step; and it is derived from the space's existing `role_name`, so every site
# already running keeps the role it has. A space's **default** role is
# `role_name` unchanged, which is precisely what a space meant before it could
# ship more than one — so the whole change is additive on a live workspace.
# --------------------------------------------------------------------------- #

CUSTOM = "custom"


def role_key(space_code: str, key: str) -> str:
	return f"{space_code}:{key}"


def custom_key(label: str) -> str:
	return f"{CUSTOM}:{label}"


def is_custom(key: str) -> bool:
	return str(key or "").startswith(CUSTOM + ":")


def frappe_role_for(space: dict, row: dict | None = None) -> str:
	"""The Frappe role one of a space's roles becomes."""
	base = space.get("role_name") or ""
	if not row or row.get("is_default"):
		return base
	return f"{base} {row['label']}".strip()


def custom_frappe_role(label: str) -> str:
	"""A workspace's own role, namespaced so it cannot collide with a shipped
	one or with ERPNext's. `Custom` is in the name deliberately: an operator
	reading a tenant's roles should be able to tell at a glance which of them we
	shipped and which the customer built."""
	return f"OneSpace Custom {label}".strip()


def space_roles(space: dict) -> list[dict]:
	"""The roles a space offers, always at least one.

	A space that declares none is the shape every space had until now: one role
	holding everything in its manifest. Returning a synthetic default here means
	nothing downstream needs a branch for the old shape.
	"""
	rows = frappe.get_all(
		"OneSpace Space Role",
		filters={"parent": space["space_code"], "parenttype": "OneSpace Space"},
		fields=["role_key", "label", "is_default", "description"],
		order_by="idx asc",
	)
	if not rows:
		return [{
			"role_key": "member",
			"label": space.get("space_label") or space["space_code"],
			"is_default": 1,
			"description": None,
		}]

	# Exactly one default, and if the space named none the first row is it —
	# otherwise entitling an app grants an app nobody can open.
	if not any(r.get("is_default") for r in rows):
		rows[0]["is_default"] = 1
	return rows


# The role the workspace owner holds. Deliberately not System Manager: that would
# let them read site_config, which carries the signing secret this site uses to
# talk to us — enough to forge its own usage reports and credit commits. What
# they actually need (inviting users, seats, custom roles) is whitelisted methods
# we run elevated, not a Frappe admin role. See docs/ONESPACE.md, Roles.
OWNER_ROLE = "OneSpace Workspace Owner"

# Held by everyone in the workspace, the owner included. It grants nothing —
# the app roles do that — and exists to mark an account as ours.
#
# Without a marker there is no safe way to tell a removed member from a user the
# site created for its own reasons. Reconciling on "holds one of our app roles"
# looks equivalent and is not: a member of a workspace with no apps entitled yet
# holds none of them, so removing that member disabled nobody and they kept
# their sign-in.
MEMBER_ROLE = "OneSpace Workspace Member"


def permission_manifest(tenant: str) -> list[dict]:
	"""Every role the tenant site should define, and what each may touch.

	One row per (role, doctype). The tenant site writes DocPerms from this, so a
	doctype absent here is reachable by nobody — an allowlist by construction
	rather than by remembering to exclude things.
	"""
	manifest = []
	for app in spaces_for_tenant(tenant):
		if not app.get("role_name"):
			continue
		roles = space_roles(app)
		rows = frappe.get_all(
			"OneSpace Space Doctype",
			filters={"parent": app["space_code"], "parenttype": "OneSpace Space"},
			fields=["document_type", "access", "if_owner", "role"],
		)
		for row in rows:
			# A grant naming no role belongs to every role in the space. That is
			# what a manifest written before roles existed meant, and it is also
			# the honest way to say "everyone here can at least see this".
			wanted = [r for r in roles if not row.get("role") or r["role_key"] == row["role"]]
			for one in wanted:
				manifest.append({
					"role": frappe_role_for(app, one),
					"doctype": row["document_type"],
					"access": row["access"],
					"if_owner": bool(row["if_owner"]),
				})

	manifest.extend(_custom_manifest(tenant))
	return manifest


def _custom_manifest(tenant: str) -> list[dict]:
	"""The workspace's own roles, as manifest rows.

	Not re-checked against the allowlist here: `Workspace Role` refuses a grant
	outside it on save, which is where a person can be told why. Re-deriving the
	allowlist on every sync would also be circular — it is computed *from* this
	function's other half.
	"""
	rows = []
	for role in frappe.get_all(
		"Workspace Role", filters={"tenant": tenant, "is_active": 1}, fields=["name", "role_label"]
	):
		name = custom_frappe_role(role["role_label"])
		for grant in frappe.get_all(
			"Workspace Role Grant",
			filters={"parent": role["name"], "parenttype": "Workspace Role"},
			fields=["document_type", "access", "if_owner"],
		):
			rows.append({
				"role": name,
				"doctype": grant["document_type"],
				"access": grant["access"],
				"if_owner": bool(grant["if_owner"]),
			})
	return rows


def offered_roles(tenant: str) -> list[dict]:
	"""Every role this workspace may hand out, shipped and custom alike.

	One list, because the person handing them out does not care which of the two
	a role is — only what it lets somebody do. `is_default` is the half that
	needs saying: those arrive with the entitlement and are not chosen.
	"""
	offered = []
	for app in spaces_for_tenant(tenant):
		if not app.get("role_name"):
			continue
		for row in space_roles(app):
			offered.append({
				"key": role_key(app["space_code"], row["role_key"]),
				"label": row["label"],
				"description": row.get("description"),
				"space": app["space_code"],
				"space_label": app.get("space_label"),
				"is_default": bool(row.get("is_default")),
				"custom": False,
			})

	for role in frappe.get_all(
		"Workspace Role",
		filters={"tenant": tenant, "is_active": 1},
		fields=["role_label", "description"],
		order_by="role_label asc",
	):
		offered.append({
			"key": custom_key(role["role_label"]),
			"label": role["role_label"],
			"description": role.get("description"),
			"space": None,
			"space_label": None,
			"is_default": False,
			"custom": True,
		})
	return offered


def roles_for_member(tenant: str, held: str | None) -> list[str]:
	"""The Frappe roles one person should hold.

	Every space's default, because entitling an app to a workspace has to mean
	its members can open it — then whatever else was ticked for this person. A
	key that names a role the workspace no longer offers is dropped rather than
	failing: spaces get un-entitled and custom roles get deleted, and neither
	should be able to wedge a sync.
	"""
	by_key = {}
	defaults = []
	for app in spaces_for_tenant(tenant):
		if not app.get("role_name"):
			continue
		for row in space_roles(app):
			name = frappe_role_for(app, row)
			by_key[role_key(app["space_code"], row["role_key"])] = name
			if row.get("is_default"):
				defaults.append(name)

	for role in frappe.get_all(
		"Workspace Role", filters={"tenant": tenant, "is_active": 1}, pluck="role_label"
	):
		by_key[custom_key(role)] = custom_frappe_role(role)

	chosen = [by_key[k] for k in _keys(held) if k in by_key]
	return sorted(set(defaults + chosen))


def _keys(held: str | None) -> list[str]:
	return [part.strip() for part in str(held or "").split(",") if part.strip()]


def allowed_doctypes(tenant: str) -> list[str]:
	"""What a customer's own role may reference.

	The same list the DocPerms come from. User, Role, DocType and the rest are
	out because they appear in no manifest, not because someone remembered to
	name them.
	"""
	return sorted({row["doctype"] for row in permission_manifest(tenant)})


def grant(tenant: str, space_code: str, note: str | None = None):
	"""Entitle a workspace to a space, and put its app on the site.

	Refused outright where the tenant's bench cannot carry what the space is
	written against — an entitlement onto a site without ERPNext is a space
	whose every screen is empty and nothing anywhere saying why, which is the
	worst of the three possible outcomes. Where the bench can and the site has
	not got there yet, an Install App job is queued and the space arrives a few
	minutes later rather than never.
	"""
	from oneapp_control.entitlements import apps

	apps.assert_can_carry(tenant, space_code)

	name = frappe.db.get_value(
		"Space Entitlement", {"tenant": tenant, "app": space_code}, "name"
	)
	if name:
		# Enabled implies offered: a space somebody is using is not one they are
		# forbidden to see, and leaving the second flag off would take it out of
		# their marketplace the moment they turned it off themselves.
		frappe.db.set_value(
			"Space Entitlement", name, {"enabled": 1, "offered": 1})
	else:
		name = frappe.get_doc(
			{
				"doctype": "Space Entitlement",
				"tenant": tenant,
				"app": space_code,
				"enabled": 1,
				"offered": 1,
				"note": note,
			}
		).insert(ignore_permissions=True).name

	apps.reconcile(tenant)
	return name


def offer(tenant: str, space_code: str, note: str | None = None):
	"""Let a workspace see a space, without turning it on for them.

	The half of the marketplace an operator drives: RUA is Restricted and
	invisible to everybody, and this is what puts it on one customer's shelf.
	Pressing the card is then theirs to do, which is what makes it a marketplace
	rather than a request form.

	Refused on the same ground `grant` is refused, and deliberately at this end
	rather than at the customer's: a card that can only ever fail is worse than
	no card, and the operator offering it is the one who can do something about
	a bench that cannot carry the app.

	Which does not make the marketplace's `unavailable` state unreachable — a
	bench is not fixed. A space offered onto one that carried its app, on a
	workspace later moved to a shard that does not, is exactly the case where a
	customer would otherwise press a button that fails.
	"""
	from oneapp_control.entitlements import apps

	apps.assert_can_carry(tenant, space_code)

	name = frappe.db.get_value(
		"Space Entitlement", {"tenant": tenant, "app": space_code}, "name"
	)
	if name:
		# `enabled` is left exactly as it is. Offering a space somebody already
		# has is a no-op, not a downgrade.
		frappe.db.set_value("Space Entitlement", name, "offered", 1)
		return name

	# No `reconcile`: nothing is installed until they press the card. That is
	# the whole point of the second flag — an offer costs a row, not minutes of
	# patches against a live database.
	return frappe.get_doc(
		{
			"doctype": "Space Entitlement",
			"tenant": tenant,
			"app": space_code,
			"enabled": 0,
			"offered": 1,
			"note": note,
		}
	).insert(ignore_permissions=True).name


def offered_spaces(tenant: str) -> list[dict]:
	"""Restricted spaces this workspace may see but has not turned on.

	What the marketplace lists beside the General ones. Enabled spaces are not
	here — they are in `spaces_for_tenant`, which is where a space they already
	have belongs.
	"""
	return frappe.db.sql(
		f"""
		SELECT {SPACE_COLUMNS}
		FROM `tabOneSpace Space` a
		INNER JOIN `tabSpace Entitlement` e ON e.app = a.name
		WHERE a.is_active = 1
		  AND a.availability = 'Restricted'
		  AND e.tenant = %(tenant)s
		  AND e.offered = 1
		  AND e.enabled = 0
		ORDER BY a.sort_order, a.space_label
		""",
		{"tenant": tenant},
		as_dict=True,
	)


def revoke(tenant: str, space_code: str):
	name = frappe.db.get_value(
		"Space Entitlement", {"tenant": tenant, "app": space_code}, "name"
	)
	if name:
		# Kept as a disabled row rather than deleted, so the history of who had
		# access to what survives.
		#
		# Both flags, and this is the whole of "take it away": leaving `offered`
		# on would put the card straight back in their marketplace with a button
		# that works, which is not what anybody means by revoke.
		frappe.db.set_value(
			"Space Entitlement", name, {"enabled": 0, "offered": 0})
