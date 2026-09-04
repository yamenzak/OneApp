"""Addresses: who may send as what, who may read what, and what it signs with.

One model for every address in a workspace, because there is only one kind of
thing here and inventing three would mean three sets of permissions to keep in
step:

    Email Account   an address
    User Email      a person's access to one

Both are Frappe's, and that is the point. `User Email` is a child table on
`User` pointing at an `Email Account`, so a person has many addresses and an
address has many people — which is exactly a shared mailbox, a decade old, and
nothing we had to design. `Email Account.signature` is the signature. What is
ours is the *granting*: a screen that writes those rows, and the rules about
which addresses a workspace may mint at all.

Three kinds, told apart by nothing more than their local part and who is
granted them:

* **The workspace's own** — one address that outbound notifications leave from.
  Set, it becomes the default outgoing account; unset, the platform's own
  sending identity stays and nothing breaks.
* **A person's** — `alice@<slug>.4dl.app`, granted to exactly one member.
* **A shared one** — `sales@<slug>.4dl.app`, granted to several.

Addresses on our own domain need no registry, and it is worth writing down why
the obvious worry does not apply: the tenant's slug is *in the domain*, so two
workspaces both wanting `sales@` get `sales@acme.4dl.app` and
`sales@globex.4dl.app` and never collide. The routing map is keyed by that slug
already. A global registry would be solving a problem the domain shape solved.

An address on the customer's *own* domain is a different matter — see
`verify.py`. Nothing sends from one until the DNS says we may.
"""

import re

import frappe
from frappe import _

from oneapp.oneapp_core.workspace import OWNER_ROLE, SUPPORT_ROLE

# The account the platform itself sends from, created by `outbound.py`. It is
# not an address a workspace owns and never appears in these lists: a manager
# who could rename or delete it could stop their own password resets arriving.
from oneapp.oneapp_core.email.outbound import ACCOUNT_NAME as PLATFORM_ACCOUNT

# What a local part may be. Deliberately narrower than RFC 5321, which permits
# quoted strings and characters that make a shell script somewhere else wrong:
# this is a name a person types into a form, and every mail system in the world
# handles this subset.
LOCAL_PART = re.compile(r"^[a-z0-9]([a-z0-9._-]{0,62}[a-z0-9])?$")

# Local parts a workspace may not take. `postmaster` and `abuse` are required to
# reach a human by RFC 2142 and are ours to answer; the rest are the ones a
# phisher would want and the ones our own machinery already uses.
RESERVED = frozenset(
	{
		"postmaster", "abuse", "hostmaster", "webmaster", "security",
		"noreply", "no-reply", "mailer-daemon", "bounce", "bounces",
		"admin", "administrator", "root", "system", "onespace",
	}
)


def _require_admin():
	roles = set(frappe.get_roles())
	if not roles & {OWNER_ROLE, SUPPORT_ROLE}:
		frappe.throw(_("Only a workspace admin can manage addresses."), frappe.PermissionError)


def domain() -> str:
	"""The workspace's own subdomain of the platform's mail domain.

	`<slug>.4dl.app`, which is the same host the site answers on — so an address
	is readable as belonging to this workspace and the inbound Worker resolves
	the tenant from the domain without a lookup table of addresses.
	"""
	conf = frappe.conf
	slug = conf.get("oneapp_tenant_slug") or conf.get("oneapp_tenant") or ""
	root = conf.get("oneapp_tenant_domain") or "4dl.app"
	return f"{slug}.{root}" if slug else root


def is_ours(email_id: str) -> bool:
	"""Whether an address is on the domain we route, rather than a customer's."""
	return (email_id or "").lower().endswith("@" + domain())


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

def _people(account: str) -> list[str]:
	"""Who has been granted an address, by `User Email` row."""
	return frappe.get_all(
		"User Email", filters={"email_account": account}, pluck="parent", distinct=True
	)


def _as_row(doc) -> dict:
	return {
		"name": doc.name,
		"email_id": doc.email_id,
		"label": doc.email_account_name,
		"ours": is_ours(doc.email_id),
		"signature": doc.signature or "",
		"add_signature": int(doc.add_signature or 0),
		"default_outgoing": int(doc.default_outgoing or 0),
		"enable_outgoing": int(doc.enable_outgoing or 0),
		"enable_incoming": int(doc.enable_incoming or 0),
		# Where mail to this address files itself. Empty means "nowhere in
		# particular", which is a Communication against no document and is the
		# right answer for a person's own address.
		"append_to": doc.append_to or "",
		"granted_to": sorted(_people(doc.name)),
	}


@frappe.whitelist(methods=["GET"])
def listing() -> dict:
	"""Every address this workspace owns, and who may use each.

	Readable by any member, not only an admin: a person needs to know which
	addresses they have been given, and hiding the rest would make "why can
	Sam send as sales@ and I cannot" unanswerable without asking somebody.
	Changing any of it still needs an admin.
	"""
	rows = []
	for name in frappe.get_all("Email Account", pluck="name"):
		if name == PLATFORM_ACCOUNT:
			continue
		rows.append(_as_row(frappe.get_doc("Email Account", name)))

	roles = set(frappe.get_roles())
	return {
		"addresses": sorted(rows, key=lambda r: r["email_id"]),
		"domain": domain(),
		"reserved": sorted(RESERVED),
		"can_manage": bool(roles & {OWNER_ROLE, SUPPORT_ROLE}),
		"members": _members(),
	}


def _members() -> list[dict]:
	"""Who could be granted an address — enabled people, not every User row."""
	return frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User"},
		fields=["name", "full_name"],
		order_by="full_name asc",
	)


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

def validate_local_part(local_part: str) -> str:
	local_part = (local_part or "").strip().lower()
	if not LOCAL_PART.match(local_part):
		frappe.throw(
			_(
				"An address may use letters, numbers, dots, dashes and "
				"underscores, and must start and end with a letter or number."
			)
		)
	if local_part in RESERVED:
		frappe.throw(_("“{0}” is reserved.").format(local_part))
	return local_part


@frappe.whitelist(methods=["POST"])
def create(local_part: str, label: str = "", grant_to: str | list | None = None) -> dict:
	"""Mint an address on the workspace's own domain.

	Outgoing only, and `enable_incoming` stays off on purpose: incoming here is
	not a mailbox being polled, it is the Worker pushing a message that has
	already arrived (see `inbound.py`). Turning the framework's IMAP poller on
	for an address with no IMAP server behind it would give a broken connection
	test and a scheduled job that fails forever.
	"""
	_require_admin()

	local_part = validate_local_part(local_part)
	email_id = f"{local_part}@{domain()}"

	if frappe.db.exists("Email Account", {"email_id": email_id}):
		frappe.throw(_("{0} already exists.").format(email_id))

	from oneapp.oneapp_core.email import outbound

	account = frappe.get_doc(
		{
			"doctype": "Email Account",
			"email_account_name": label or local_part,
			"email_id": email_id,
			# The same Cloudflare transport the platform's own account uses.
			# An address with `enable_outgoing` and no server is one Frappe
			# accepts, offers in the picker, and fails on at the first send.
			**outbound.transport(),
			"enable_outgoing": 1,
			"enable_incoming": 0,
			"always_use_account_email_id_as_sender": 1,
		}
	)
	account.insert(ignore_permissions=True)

	for user in _wanted(grant_to):
		grant(account.name, user)

	return _as_row(frappe.get_doc("Email Account", account.name))


def _wanted(grant_to) -> list[str]:
	if not grant_to:
		return []
	if isinstance(grant_to, str):
		grant_to = frappe.parse_json(grant_to) if grant_to.startswith("[") else [grant_to]
	return [one for one in grant_to if one]


@frappe.whitelist(methods=["POST"])
def update(name: str, label: str | None = None, signature: str | None = None,
           add_signature: int | None = None, append_to: str | None = None) -> dict:
	"""Change an address's own settings.

	The signature is the one thing here a *member* may change on an address they
	hold, rather than only an admin — it is their name at the bottom of their
	own mail. Everything else is the workspace's.
	"""
	account = _account(name)

	if signature is not None or add_signature is not None:
		_require_holder_or_admin(account.name)
		if signature is not None:
			account.signature = signature
		if add_signature is not None:
			account.add_signature = int(add_signature)

	if label is not None or append_to is not None:
		_require_admin()
		if label is not None:
			account.email_account_name = label
		if append_to is not None:
			account.append_to = append_to or None

	account.save(ignore_permissions=True)
	return _as_row(account)


def _account(name: str):
	if name == PLATFORM_ACCOUNT:
		frappe.throw(_("The platform's own address cannot be changed here."))
	if not frappe.db.exists("Email Account", name):
		frappe.throw(_("No such address."), frappe.DoesNotExistError)
	return frappe.get_doc("Email Account", name)


def _require_holder_or_admin(account: str):
	roles = set(frappe.get_roles())
	if roles & {OWNER_ROLE, SUPPORT_ROLE}:
		return
	if frappe.session.user not in _people(account):
		frappe.throw(_("That address is not yours."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def remove(name: str) -> dict:
	"""Delete an address, and every grant to it.

	Mail already received is *not* deleted — a `Communication` is a record of
	something that happened, and losing the correspondence because somebody
	tidied up an address would be the worst kind of surprise. It stops being
	reachable, which is what deleting an address means.
	"""
	_require_admin()
	account = _account(name)

	if account.default_outgoing:
		frappe.throw(
			_("This is the workspace's sending address. Choose another one first.")
		)

	for row in frappe.get_all("User Email", filters={"email_account": account.name},
	                          fields=["name", "parent"]):
		frappe.db.delete("User Email", row["name"])

	frappe.delete_doc("Email Account", account.name, ignore_permissions=True, force=True)
	return {"ok": True, "removed": name}


# --------------------------------------------------------------------------- #
# Access
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def grant(name: str, user: str) -> dict:
	"""Give somebody an address. Idempotent — granting twice is granting once."""
	_require_admin()
	account = _account(name)

	if not frappe.db.exists("User", user):
		frappe.throw(_("No such person."), frappe.DoesNotExistError)

	if frappe.db.exists("User Email", {"parent": user, "email_account": account.name}):
		return {"ok": True, "already": True}

	person = frappe.get_doc("User", user)
	person.append(
		"user_emails",
		{
			"email_account": account.name,
			"email_id": account.email_id,
			"enable_outgoing": int(account.enable_outgoing or 0),
		},
	)
	person.save(ignore_permissions=True)
	return {"ok": True, "granted": user}


@frappe.whitelist(methods=["POST"])
def revoke(name: str, user: str) -> dict:
	"""Take an address back.

	The rows go, and so does the ability to read what arrived on it — see
	`inbound.py`, where a Communication is shared with whoever holds the
	address at the time it lands. Anything already shared with them stays
	shared, which is the framework's own rule for `DocShare` and the one we do
	not want to be different from: revoking access to a mailbox is not the same
	promise as unsending what somebody has already read.
	"""
	_require_admin()
	account = _account(name)

	rows = frappe.get_all(
		"User Email", filters={"parent": user, "email_account": account.name}, pluck="name"
	)
	for row in rows:
		frappe.db.delete("User Email", row)

	return {"ok": True, "revoked": user, "rows": len(rows)}


# --------------------------------------------------------------------------- #
# The workspace's sending address
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def set_default(name: str = "") -> dict:
	"""Which address the workspace's own mail leaves from.

	Empty puts it back to the platform's, which is the state every workspace
	starts in and the one that always works. Frappe allows exactly one
	`default_outgoing`, so this clears the others rather than trusting the
	caller to.
	"""
	_require_admin()

	for other in frappe.get_all("Email Account", filters={"default_outgoing": 1}, pluck="name"):
		frappe.db.set_value("Email Account", other, "default_outgoing", 0)

	if not name:
		# Back to ours. It is the account that actually holds the Cloudflare
		# token, so it can always send.
		if frappe.db.exists("Email Account", PLATFORM_ACCOUNT):
			frappe.db.set_value("Email Account", PLATFORM_ACCOUNT, "default_outgoing", 1)
		return {"ok": True, "default": PLATFORM_ACCOUNT}

	account = _account(name)
	if not account.enable_outgoing:
		frappe.throw(_("{0} is not set up to send.").format(account.email_id))
	if not is_ours(account.email_id) and not _verified(account.email_id):
		frappe.throw(
			_(
				"{0} is on a domain we have not verified yet. Publish the DNS "
				"records first."
			).format(account.email_id)
		)

	frappe.db.set_value("Email Account", account.name, "default_outgoing", 1)
	return {"ok": True, "default": account.name}


def _verified(email_id: str) -> bool:
	from oneapp.oneapp_core.email import verify

	return verify.is_verified((email_id or "").split("@")[-1])
