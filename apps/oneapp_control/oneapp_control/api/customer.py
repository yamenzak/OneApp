"""Customer self-service.

One account may own several workspaces — signing up for a company and later for
something at home is ordinary, and forcing a second email for it is friction
people remember. Each workspace carries its own plan, subscription and ledger.

That makes the isolation rule slightly weaker than "no parameter at all", so it
is concentrated in one function rather than repeated at every call site:

    every endpoint that touches a workspace calls require_workspace(),
    which verifies ownership before returning anything.

There is no path that trusts a name from the request. Tests read this module and
fail the build if an endpoint reaches a workspace any other way.
"""

import frappe
from frappe import _

from oneapp_control import portal
from oneapp_control.billing import checkout
from oneapp_control.billing import packs as pack_catalogue, quotas, stripe_client
from oneapp_control.credits import ledger
from oneapp_control.entitlements import registry


def require_workspace(workspace: str | None):
	"""Resolve a workspace the caller owns, or refuse.

	The single ownership check in the customer surface. Raises rather than
	returning None so no caller can proceed on an empty result.

	The workspace is optional in the signature of every endpoint that takes one,
	so that *this* answers a missing one. A required parameter meant Frappe
	raised a TypeError first — a 500 in the log on every load of a screen whose
	resource fetches once before the workspace switcher has resolved, which is
	the normal first render rather than a fault.
	"""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please sign in."), frappe.PermissionError)

	if not workspace:
		frappe.throw(_("No workspace specified."), frappe.PermissionError)

	owner = frappe.db.get_value("Tenant", workspace, "owner_user")

	# Same error whether the workspace belongs to someone else or does not
	# exist: a customer must not be able to probe for which names are taken.
	if owner != user:
		frappe.throw(_("Workspace not found."), frappe.PermissionError)

	return frappe.get_doc("Tenant", workspace)


@frappe.whitelist()
def my_workspaces() -> list[dict]:
	"""Every workspace this account owns. The switcher reads this."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please sign in."), frappe.PermissionError)

	rows = frappe.get_all(
		"Tenant",
		filters={"owner_user": user},
		fields=["name", "tenant_name", "tenant_slug", "status", "plan", "site_name", "region"],
		order_by="creation asc",
	)
	for row in rows:
		row["url"] = f"https://{row['site_name']}" if row["site_name"] else None
	return rows


@frappe.whitelist()
def overview(workspace: str | None = None) -> dict:
	"""Everything the account page shows for one workspace, in one call."""
	tenant = require_workspace(workspace)
	plan = frappe.get_doc("Plan", tenant.plan) if tenant.plan else None

	subscription = None
	if tenant.subscription:
		sub = frappe.get_doc("Subscription", tenant.subscription)
		subscription = {
			"status": sub.status,
			"interval": sub.interval,
			"current_period_end": str(sub.current_period_end) if sub.current_period_end else None,
			"cancel_at_period_end": bool(sub.cancel_at_period_end),
		}

	return {
		"workspace": {
			"name": tenant.name,
			"title": tenant.tenant_name,
			"slug": tenant.tenant_slug,
			"status": tenant.status,
			"url": f"https://{tenant.site_name}" if tenant.site_name else None,
			"custom_domain": tenant.primary_domain,
			"region": tenant.region,
			"storage_jurisdiction": tenant.storage_jurisdiction,
		},
		"plan": {
			"code": tenant.plan,
			"name": plan.plan_name if plan else None,
			"audience": plan.audience if plan else None,
			"price_monthly": plan.price_monthly if plan else None,
		},
		"subscription": subscription,
		"usage": usage_for(tenant),
		# Where this workspace stands if it has stopped being paid for, and what
		# happens next. Shown to the customer rather than only to us: the whole
		# point of the ladder is that nobody is surprised, and an email they
		# missed is the only other place these dates appear.
		"lifecycle": lifecycle_for(tenant),
		"backups": backups_for(tenant),
		"credits": {
			"balance": ledger.balance(tenant.name),
			"available": ledger.available(tenant.name),
		},
	}


def lifecycle_for(tenant) -> dict:
	"""What is scheduled to happen to this workspace, in the customer's terms.

	Empty when nothing is: a workspace that is paid for should not carry a panel
	explaining what would happen if it were not.
	"""
	from oneapp_control.lifecycle import overage, policy

	quota = overage.state(tenant)
	if not tenant.dunning_started_on and not quota.get("over"):
		return {}

	windows = policy.windows()
	from frappe.utils import add_to_date, getdate

	found = {"stage": tenant.dunning_stage, "over_quota": quota}

	if tenant.dunning_started_on:
		found["unpaid_since"] = str(tenant.dunning_started_on)
		found["suspends_on"] = add_to_date(
			getdate(tenant.dunning_started_on),
			days=windows["dunning_grace_days"],
			as_string=True,
		)
	if tenant.suspended_on:
		found["archives_on"] = add_to_date(
			getdate(tenant.suspended_on), days=windows["suspended_days"], as_string=True
		)
	if tenant.purge_after:
		found["deleted_on"] = str(tenant.purge_after)
	if tenant.cold_storage_key:
		found["restorable"] = True

	return found


def backups_for(tenant) -> dict:
	"""What is being kept, and when the last one landed.

	A plan term people are paying for and could not otherwise see. It is also
	the fastest way for somebody to notice their workspace has quietly stopped
	backing up, which matters more to them than it does to us.
	"""
	from oneapp_control.billing import quotas

	terms = quotas.for_tenant(tenant)
	return {
		"per_day": int(terms.get("backups_per_day") or 0),
		"retention_days": int(terms.get("backup_retention_days") or 0),
		"last_on": str(tenant.last_backup_on) if tenant.last_backup_on else None,
		"last_bytes": tenant.last_backup_bytes or 0,
	}


def usage_for(tenant) -> dict:
	"""Usage against quota, with the warning threshold already applied.

	Computed server-side so both SPAs and any future surface agree on when a
	workspace is 'nearly full'.
	"""
	from oneapp_control.control_plane.doctype.tenant.tenant import WARN_FRACTION

	def bucket(used, quota):
		fraction = (used / quota) if quota else 0
		return {
			"used": used,
			"quota": quota,
			"fraction": round(fraction, 4),
			"warn": bool(quota) and fraction >= WARN_FRACTION,
			"exceeded": bool(quota) and used >= quota,
		}

	return {
		"storage": bucket(tenant.storage_used_bytes or 0, tenant.storage_quota_bytes),
		"database": bucket(tenant.database_used_bytes or 0, tenant.database_quota_bytes),
		"users": bucket(tenant.user_count or 0, tenant.max_users),
	}


@frappe.whitelist()
def credit_history(workspace: str, limit: int = 50) -> list[dict]:
	"""This workspace's own credit ledger, newest first."""
	tenant = require_workspace(workspace)
	return frappe.get_all(
		"Credit Ledger Entry",
		filters={"tenant": tenant.name},
		fields=["creation", "entry_type", "credits", "expires_on", "remarks"],
		order_by="creation desc",
		limit=min(int(limit), 200),
	)


@frappe.whitelist()
def invoices(workspace: str, limit: int = 24) -> list[dict]:
	"""This workspace's own invoices."""
	tenant = require_workspace(workspace)
	if not tenant.customer:
		return []

	return frappe.get_all(
		"Sales Invoice",
		filters={"customer": tenant.customer, "docstatus": 1},
		fields=["name", "posting_date", "grand_total", "currency", "status"],
		order_by="posting_date desc",
		limit=min(int(limit), 100),
	)


@frappe.whitelist()
def packs() -> dict:
	"""What credit packs are for sale.

	Read from the `Credit Pack` catalogue rather than a list in this file, so
	changing a price is an edit an operator makes rather than a deploy. Storage
	is not here any more: it is an add-on now, bought per month against the
	subscription, and `addons()` below answers for it.
	"""
	return {"credits": pack_catalogue.offered()}


@frappe.whitelist()
def buy_credits(workspace: str, pack: str, code: str | None = None) -> dict:
	"""Start checkout for a pack, named by code.

	The code and nothing else. What it costs is looked up server-side, because
	accepting an amount from the caller would let anyone buy a million credits
	for a penny.
	"""
	tenant = require_workspace(workspace)
	return checkout.start_credit_pack(tenant.name, pack, code)


@frappe.whitelist(methods=["GET"])
def addons(workspace: str | None = None) -> dict:
	"""What extra quota is for sale, and how much of it this workspace holds.

	Both together rather than two calls: a stepper needs the catalogue and the
	current quantity in the same render, and fetching them separately is how one
	arrives a frame after the other and the control jumps.

	Priced at the cadence this workspace bills on. Stripe requires every
	recurring line on one subscription to share an interval, so an add-on with no
	price at that cadence is genuinely not available here — reported as such
	rather than silently dropped, because "where did it go" is a support ticket.
	"""
	tenant = require_workspace(workspace)
	interval = (
		frappe.db.get_value("Subscription", tenant.subscription, "interval")
		if tenant.subscription
		else None
	) or "Monthly"

	held = {
		row["addon"]: row
		for row in (
			frappe.get_all(
				"Subscription Add-on",
				filters={"parent": tenant.subscription, "parenttype": "Subscription"},
				fields=["addon", "quantity", "unit_gb", "unit_amount", "currency"],
			)
			if tenant.subscription
			else []
		)
	}

	offered = []
	for row in frappe.get_all(
		"Add-on",
		filters={"is_active": 1},
		fields=["name", "addon_name", "kind", "unit_gb", "max_units", "currency",
		        "price_monthly", "price_yearly", "description",
		        "stripe_price_id_monthly", "stripe_price_id_yearly"],
		order_by="sort_order asc, addon_name asc",
	):
		mine = held.get(row["name"])
		price = row["price_yearly"] if interval == "Yearly" else row["price_monthly"]
		offered.append({
			"code": row["name"],
			"name": row["addon_name"],
			"kind": row["kind"],
			"unit_gb": row["unit_gb"],
			"max_units": row["max_units"],
			"currency": row["currency"],
			"amount": price,
			"description": row["description"],
			"quantity": int(mine["quantity"]) if mine else 0,
			# What they are actually paying per unit, which is not the catalogue
			# price once a rate has been grandfathered.
			"held_amount": mine["unit_amount"] if mine else None,
			"held_unit_gb": mine["unit_gb"] if mine else None,
			"available": bool(
				row["stripe_price_id_yearly" if interval == "Yearly" else "stripe_price_id_monthly"]
			),
		})

	return {
		"interval": interval,
		"addons": offered,
		# Nothing to hang a line from. The page says so rather than offering
		# controls that would refuse.
		"can_buy": bool(tenant.subscription),
	}


@frappe.whitelist(methods=["POST"])
def set_addon(workspace: str, addon: str, quantity: int,
              code: str | None = None) -> dict:
	"""Hold this many units. Zero releases it."""
	tenant = require_workspace(workspace)
	return checkout.set_addon_quantity(tenant.name, addon, quantity, code)


@frappe.whitelist()
def billing_portal(workspace: str) -> dict:
	"""Hand the customer to Stripe for card and cancellation management."""
	tenant = require_workspace(workspace)
	if not tenant.subscription:
		frappe.throw(_("No subscription to manage yet."))

	customer_id = frappe.db.get_value("Subscription", tenant.subscription, "stripe_customer_id")
	if not customer_id:
		frappe.throw(_("No Stripe customer on this subscription."))

	session = stripe_client.create_billing_portal_session(
		customer_id, portal.account_url(tenant.name, "billing")
	)
	return {"url": session.get("url")}


@frappe.whitelist()
def domain_instructions(workspace: str | None = None) -> dict:
	"""What the customer has to do in their own DNS, and how it is going.

	Written out rather than linked because the two ways this fails — a proxied
	record and an apex domain — are both invisible from our side and produce an
	error that points elsewhere.
	"""
	tenant = require_workspace(workspace)

	pending = frappe.get_all(
		"Provisioning Job",
		filters={
			"tenant": tenant.name,
			"action": "Add Domain",
			"state": ("in", ("Requested", "Running", "Awaiting Agent")),
		},
		fields=["name", "state", "last_error", "payload"],
		order_by="creation desc",
		limit=1,
	)

	return {
		"target": tenant.site_name,
		"current": tenant.primary_domain,
		"pending": pending[0] if pending else None,
		"steps": [
			{
				"title": "Add a CNAME in your DNS",
				"detail": f"Point your subdomain at {tenant.site_name}.",
			},
			{
				"title": "Turn the proxy off",
				"detail": (
					"On Cloudflare the record must be DNS-only — grey cloud. A "
					"proxied record resolves to Cloudflare instead of your site, "
					"and the certificate cannot be issued."
				),
			},
			{
				"title": "Use a subdomain",
				"detail": (
					"app.yourcompany.com works; yourcompany.com on its own cannot, "
					"because an apex domain cannot hold a CNAME."
				),
			},
			{
				"title": "Add it here",
				"detail": "We verify the record and issue a certificate. Usually a minute or two.",
			},
		],
	}


@frappe.whitelist()
def request_custom_domain(workspace: str, domain: str) -> str:
	"""Ask for a custom domain. An operator points it; this records the ask."""
	tenant = require_workspace(workspace)
	domain = (domain or "").strip().lower().rstrip(".")

	if not domain or "." not in domain or " " in domain:
		frappe.throw(_("Enter a domain such as app.yourcompany.com."))
	if domain.endswith(".4dl.app"):
		frappe.throw(_("That is already your workspace address."))

	from oneapp_control.provisioning import runner

	return runner.enqueue(
		tenant.name,
		"Add Domain",
		{"domain": domain},
		idempotency_key=f"domain:{tenant.name}:{domain}",
	).name


# --------------------------------------------------------------------------- #
# People
#
# The control plane cannot write into a tenant's database — the signed sync is
# the only channel and it runs one way — so an invite is a row here and the
# tenant site reconciles its own Users against it. That is the same route the
# owner account already takes, and it means an invite is live on the next sync
# rather than immediately. `members()` says so rather than pretending otherwise.
# --------------------------------------------------------------------------- #

ACCESS_LEVELS = ("Member", "Admin")


def _seats(tenant) -> dict:
	"""Seats used and allowed. The owner holds one; members hold the rest.

	Counted from this list rather than from `Tenant.user_count`, which is what
	the workspace's site last reported. The two agree once a sync has run, and
	before that this one is right: an invite made a minute ago is a seat that is
	taken, and enforcing against the older number would let a plan be
	over-subscribed in the window between inviting and syncing.
	"""
	used = 1 + len(tenant.members or [])
	quota = tenant.max_users or 0
	return {"used": used, "quota": quota, "remaining": max(quota - used, 0) if quota else None}


def _role_keys(held) -> list[str]:
	return [part.strip() for part in str(held or "").split(",") if part.strip()]


def _validated_roles(tenant, roles) -> str:
	"""The role keys a workspace may actually hand out, as the field stores them.

	Checked against `offered_roles` rather than taken on trust. The keys travel
	from a browser, and an unknown one would be silently dropped at sync time —
	which reads as "I ticked it and nothing happened" and is the worst way to
	find out. Better to refuse and say which.

	Defaults are not stored: every space's default arrives with the entitlement
	(`roles_for_member`), so writing them down here would mean a role removed
	from a space lingers on every member who was invited while it existed.
	"""
	from oneapp_control.entitlements import registry

	if roles is None:
		return ""
	if isinstance(roles, str):
		wanted = _role_keys(roles)
	else:
		wanted = [str(one).strip() for one in roles if str(one).strip()]

	offered = {r["key"]: r for r in registry.offered_roles(tenant.name)}
	unknown = [key for key in wanted if key not in offered]
	if unknown:
		frappe.throw(
			_("This workspace does not offer {0}.").format(", ".join(sorted(unknown)))
		)

	return ",".join(sorted({key for key in wanted if not offered[key]["is_default"]}))


@frappe.whitelist(methods=["POST"])
def set_member_roles(workspace: str, email: str, roles: str | list | None = None,
                     access: str | None = None) -> dict:
	"""Change what one person may do.

	Roles and access together, because they are one decision on one screen —
	`access` is the workspace-wide half (may they manage the workspace) and the
	roles are the per-app half.
	"""
	tenant = require_workspace(workspace)
	email = (email or "").strip().lower()

	if email == (tenant.owner_email or "").strip().lower():
		# The owner's reach is not a role. They hold the workspace, they are the
		# billing contact, and a screen that let somebody demote them would let
		# a workspace lock itself out of its own subscription.
		frappe.throw(_("The workspace owner's access cannot be changed here."))

	row = next(
		(r for r in tenant.members or [] if (r.email or "").strip().lower() == email), None
	)
	if not row:
		frappe.throw(_("{0} is not a member of this workspace.").format(email))

	if access is not None:
		if access not in ACCESS_LEVELS:
			frappe.throw(_("Unknown access level {0}.").format(access))
		row.access = access

	row.roles = _validated_roles(tenant, roles)
	tenant.save(ignore_permissions=True)
	frappe.db.commit()

	return members(workspace)


@frappe.whitelist(methods=["GET"])
def members(workspace: str | None = None) -> dict:
	"""Everyone who can sign in to the workspace, the owner first."""
	tenant = require_workspace(workspace)

	people = [
		{
			"email": tenant.owner_email,
			"full_name": tenant.tenant_name,
			"access": "Owner",
			"is_owner": True,
			"invited_on": tenant.creation,
		}
	]
	from oneapp_control.entitlements import registry

	offered = {r["key"] for r in registry.offered_roles(tenant.name)}
	people += [
		{
			"email": row.email,
			"full_name": row.full_name or "",
			"access": row.access,
			"is_owner": False,
			"invited_on": row.invited_on,
			# The keys, not the resolved Frappe roles: this list is what the
			# picker ticks against, and the Frappe names are an implementation
			# detail of the site this person will sign in to.
			#
			# Narrowed to what is still offered. A key outlives the role it
			# names — deleting a custom role deliberately leaves it on whoever
			# held it, because `roles_for_member` drops what it does not
			# recognise and that is what makes the delete safe. Showing the
			# stale key here would put a tick beside a role that no longer
			# exists, and saving that back would be refused by
			# `_validated_roles` for a box the person never touched.
			"roles": [key for key in _role_keys(row.roles) if key in offered],
		}
		for row in (tenant.members or [])
	]

	return {
		"members": people,
		"seats": _seats(tenant),
		"access_levels": list(ACCESS_LEVELS),
		# Everything this workspace may hand out, shipped and custom alike. Sent
		# with the members because the two are read together — you are looking
		# at a person to decide what they may do.
		"roles": registry.offered_roles(tenant.name),
		# An invite becomes an account on the workspace's next sync, not now.
		# Saying so is the difference between "slow" and "broken".
		"last_synced": tenant.usage_synced_on,
	}


@frappe.whitelist(methods=["POST"])
def invite_member(workspace: str, email: str, full_name: str = "", access: str = "Member",
                  roles: str | list | None = None) -> dict:
	"""Add someone to the workspace, within the plan's seat count."""
	tenant = require_workspace(workspace)

	email = (email or "").strip().lower()
	if not email:
		frappe.throw(_("An email address is required."))
	frappe.utils.validate_email_address(email, throw=True)

	if access not in ACCESS_LEVELS:
		frappe.throw(_("Unknown access level {0}.").format(access))

	if email == (tenant.owner_email or "").strip().lower():
		frappe.throw(_("{0} owns this workspace already.").format(email))

	if any((row.email or "").strip().lower() == email for row in tenant.members or []):
		frappe.throw(_("{0} is already a member.").format(email))

	seats = _seats(tenant)
	if seats["quota"] and seats["used"] >= seats["quota"]:
		# Refused here rather than at the tenant site, where the person would
		# already have had a welcome email for an account that cannot exist.
		frappe.throw(
			_("This plan includes {0} seats and all are in use. Change plan to add more.").format(
				seats["quota"]
			)
		)

	tenant.append(
		"members",
		{
			"email": email,
			"full_name": (full_name or "").strip(),
			"access": access,
			"roles": _validated_roles(tenant, roles),
			"invited_on": frappe.utils.now_datetime(),
		},
	)
	tenant.save(ignore_permissions=True)
	frappe.db.commit()

	return members(workspace)


@frappe.whitelist(methods=["POST"])
def remove_member(workspace: str, email: str) -> dict:
	"""Take someone out of the workspace.

	The row goes; the tenant site disables that User on its next sync rather
	than deleting it, because the documents they created are the workspace's and
	Frappe hangs ownership off the account.
	"""
	tenant = require_workspace(workspace)
	email = (email or "").strip().lower()

	if email == (tenant.owner_email or "").strip().lower():
		frappe.throw(_("The owner cannot be removed from their own workspace."))

	remaining = [row for row in (tenant.members or []) if (row.email or "").strip().lower() != email]
	if len(remaining) == len(tenant.members or []):
		frappe.throw(_("{0} is not a member of this workspace.").format(email))

	tenant.members = []
	for row in remaining:
		tenant.append(
			"members",
			{
				"email": row.email,
				"full_name": row.full_name,
				"access": row.access,
				"invited_on": row.invited_on,
			},
		)
	tenant.save(ignore_permissions=True)
	frappe.db.commit()

	return members(workspace)


# --------------------------------------------------------------------------- #
# What the workspace has, and what changing plan would give it
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def apps(workspace: str | None = None) -> dict:
	"""The apps this workspace can open.

	The same manifest the launcher renders, so a customer looking at their
	account sees exactly what they see when they sign in. `included` separates
	what every plan carries from what was granted to them specifically —
	otherwise "why do we have this?" has no answer on this page.
	"""
	tenant = require_workspace(workspace)

	granted = set(
		frappe.get_all(
			"Space Entitlement",
			filters={"tenant": tenant.name, "enabled": 1},
			pluck="app",
		)
	)

	return {
		"apps": [
			{
				"code": app["space_code"],
				"label": app["space_label"],
				"icon": app.get("icon"),
				"included": app["space_code"] not in granted,
			}
			for app in registry.spaces_for_tenant(tenant.name)
		],
		"workspace_url": f"https://{tenant.primary_domain or tenant.site_name}"
		if (tenant.primary_domain or tenant.site_name)
		else None,
	}


@frappe.whitelist(methods=["POST"])
def change_plan(workspace: str, plan: str, interval: str = "Monthly") -> dict:
	"""Move this workspace onto another plan.

	Through us rather than Stripe's billing portal, because the portal cannot
	know our quotas: it would sell a downgrade to a workspace already holding
	more than the smaller plan allows, and the customer would find out
	afterwards, over quota. `billing.checkout.change_plan` runs the same fit
	check this page renders.
	"""
	tenant = require_workspace(workspace)
	return checkout.change_plan(tenant.name, plan, interval)


@frappe.whitelist(methods=["GET"])
def plans(workspace: str | None = None) -> dict:
	"""What this workspace is on, and what else it could be on.

	Every plan carries every feature — they differ only in quotas, which is why
	no feature flags exist anywhere in this codebase (docs/ONEADMIN.md, Plans). So the
	comparison is the numbers, and a plan that would not fit what the workspace
	already uses is marked rather than merely listed: finding out a downgrade is
	impossible *after* choosing it is the worst version of this page.
	"""
	tenant = require_workspace(workspace)
	usage = usage_for(tenant)

	fields = [
		"name", "plan_name", "audience", "currency",
		"price_monthly", "price_yearly",
		"storage_gb", "database_gb", "max_users", "monthly_credit_grant",
		"description",
	]

	# Two queries rather than one with `or_filters`: Frappe ANDs or_filters onto
	# filters rather than ORing the whole clause, so `is_active=1` plus
	# `name=<current>` resolved to just the current plan and the page offered
	# nothing to move to.
	rows = frappe.get_all(
		"Plan", filters={"is_active": 1}, fields=fields, order_by="sort_order asc"
	)

	# A workspace on a plan that has since been retired still has to see what it
	# is on — a page that cannot tell you that is worse than one showing a plan
	# nobody else can buy.
	if tenant.plan and not any(row.name == tenant.plan for row in rows):
		retired = frappe.get_all("Plan", filters={"name": tenant.plan}, fields=fields)
		rows = retired + rows

	# What this workspace is actually on may differ from what its plan says
	# today, because the terms were captured when it was sold. The current card
	# has to show the terms in force, not the price sheet.
	in_force = quotas.for_tenant(tenant)

	available = []
	for row in rows:
		current = row.name == tenant.plan
		terms = in_force if current else {
			field: row.get(field) for field in quotas.TERMS if field in row
		}
		available.append(
			{
				"code": row.name,
				"name": row.plan_name,
				"price_monthly": row.price_monthly,
				"price_yearly": row.price_yearly,
				"storage_gb": terms.get("storage_gb"),
				"database_gb": terms.get("database_gb"),
				"max_users": terms.get("max_users"),
				"monthly_credit_grant": terms.get("monthly_credit_grant"),
				"currency": row.currency,
				"audience": row.audience,
				"description": row.description,
				"current": current,
				# The same check the switch itself runs, so the page cannot offer
				# a plan the switch would refuse — nor, more importantly, accept
				# one the page would have refused.
				# Named, not just refused: "storage" tells them what to clear.
				"blocked_by": [] if current else quotas.blockers(tenant, terms),
				# A plan whose terms differ from what this workspace holds is a
				# plan they are grandfathered on. Saying so beats a card that
				# quietly disagrees with the price sheet.
				"grandfathered": current and _differs(in_force, row),
			}
		)

	return {"current": tenant.plan, "plans": available, "usage": usage}


def _differs(in_force: dict, row) -> bool:
	return any(
		(in_force.get(field) or 0) != (row.get(field) or 0)
		for field in ("storage_gb", "database_gb", "max_users", "monthly_credit_grant")
	)


# --------------------------------------------------------------------------- #
# Roles the workspace builds for itself
#
# The shipped roles are what an app thinks the jobs are. A workspace that
# disagrees builds its own out of the same parts, and `allowed_doctypes` is the
# bound: the union of every doctype the workspace's own spaces expose. A custom
# role therefore cannot reach `User`, `Role` or `DocType` — they appear in no
# manifest — and cannot reach an app the workspace has not bought.
#
# `Workspace Role.validate` checks the same thing, because the operator console
# is a second door onto the same records and an allowlist one door skips is not
# an allowlist. This is where a person is told *why*, which is the part a
# validate hook is bad at.
# --------------------------------------------------------------------------- #

GRANT_LEVELS = ("Read", "Write", "Manage")


@frappe.whitelist(methods=["GET"])
def roles(workspace: str | None = None) -> dict:
	"""Every role on offer, and the parts a new one can be built from."""
	tenant = require_workspace(workspace)
	from oneapp_control.entitlements import registry

	custom = frappe.get_all(
		"Workspace Role",
		filters={"tenant": tenant.name},
		fields=["name", "role_label", "description", "is_active", "created_by_email"],
		order_by="role_label asc",
	)
	for role in custom:
		role["grants"] = frappe.get_all(
			"Workspace Role Grant",
			filters={"parent": role["name"], "parenttype": "Workspace Role"},
			fields=["space", "document_type", "access", "if_owner"],
			order_by="idx asc",
		)

	return {
		"offered": registry.offered_roles(tenant.name),
		"custom": custom,
		"available": _available_grants(tenant.name),
		"levels": list(GRANT_LEVELS),
	}


def _available_grants(tenant: str) -> list[dict]:
	"""What a custom role may reach, grouped the way somebody thinks about it.

	Named by the screen that shows it wherever there is one. A doctype is called
	`Sales Invoice` and the workspace's own navigation calls it `Invoices`, and
	the second is the word the person building a role has been looking at all
	week. Falls back to the doctype's name, which is honest rather than helpful
	and is better than inventing something.
	"""
	from oneapp_control.entitlements.registry import screens_for, spaces_for_tenant

	rows = []
	for space in spaces_for_tenant(tenant):
		labels = {
			screen["document_type"]: screen["label"]
			for screen in screens_for(space["space_code"])
			if screen.get("document_type")
		}
		seen = set()
		for grant in frappe.get_all(
			"OneSpace Space Doctype",
			filters={"parent": space["space_code"], "parenttype": "OneSpace Space"},
			fields=["document_type"],
			order_by="idx asc",
		):
			doctype = grant["document_type"]
			if doctype in seen:
				# One doctype can appear once per role in the manifest; the
				# builder offers it once.
				continue
			seen.add(doctype)
			rows.append({
				"space": space["space_code"],
				"space_label": space.get("space_label"),
				"document_type": doctype,
				"label": labels.get(doctype) or doctype,
			})
	return rows


@frappe.whitelist(methods=["POST"])
def save_role(workspace: str, role_label: str, grants: str | list,
              description: str = "", name: str | None = None) -> dict:
	"""Create or replace one of the workspace's own roles.

	Replace, not patch: the builder sends the whole grant list, so a doctype
	dropped from it is dropped from the role. A patch would need the browser and
	the server to agree about what was there before, and they cannot.
	"""
	tenant = require_workspace(workspace)
	rows = _grant_rows(grants)

	if name:
		doc = frappe.get_doc("Workspace Role", name)
		if doc.tenant != tenant.name:
			# Not "not found": a workspace asking about another workspace's role
			# has been handed an id it should not have.
			frappe.throw(_("That role belongs to another workspace."), frappe.PermissionError)
		doc.role_label = role_label
		doc.description = description
		doc.set("grants", rows)
	else:
		doc = frappe.get_doc({
			"doctype": "Workspace Role",
			"tenant": tenant.name,
			"role_label": role_label,
			"description": description,
			"is_active": 1,
			"grants": rows,
		})

	# `validate` re-checks every grant against the allowlist and refuses the
	# save, so this is the one call that has to succeed for the role to exist.
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return roles(workspace)


def _grant_rows(grants) -> list[dict]:
	rows = []
	for one in frappe.parse_json(grants) or []:
		access = one.get("access") or "Read"
		if access not in GRANT_LEVELS:
			frappe.throw(_("Unknown access level {0}.").format(access))
		rows.append({
			"space": one.get("space") or "",
			"document_type": one.get("document_type"),
			"access": access,
			"if_owner": 1 if one.get("if_owner") else 0,
		})
	if not rows:
		frappe.throw(_("A role has to grant something."))
	return rows


@frappe.whitelist(methods=["POST"])
def delete_role(workspace: str, name: str) -> dict:
	"""Remove a role the workspace built.

	The people holding it keep the key in their member row and simply stop
	resolving to anything — `roles_for_member` drops a key it does not
	recognise, which is what makes a delete safe to do while somebody holds it.
	The Frappe role itself goes on the tenant site's next sync, because it stops
	appearing in the manifest.
	"""
	tenant = require_workspace(workspace)
	doc = frappe.get_doc("Workspace Role", name)
	if doc.tenant != tenant.name:
		frappe.throw(_("That role belongs to another workspace."), frappe.PermissionError)

	doc.delete(ignore_permissions=True)
	frappe.db.commit()
	return roles(workspace)
