"""Transactional email from the control plane.

Two paths reach a customer at signup and they read very differently, so both are
written out rather than left to a generic template:

* a workspace claimed from the warm pool is ready in seconds — the email is a
  link they can use now;
* a workspace built from scratch takes minutes — the email is the thing that
  tells them it finished, and is the only reason they can close the tab.

Every send is best-effort. A workspace that exists but whose email failed is
recoverable; failing provisioning because an SMTP call timed out is not.
"""

import frappe


def _safe(fn):
	"""Never let a failed send break the thing it was reporting on.

	Returns True when the mail actually went and False when it did not, and the
	distinction matters in exactly one place: the lifecycle refuses to destroy a
	workspace that was not warned, and "warned" has to mean an email that left
	the building rather than one we attempted. See `lifecycle.sweep._purge`.
	"""
	def wrapper(*args, **kwargs):
		try:
			fn(*args, **kwargs)
			return True
		except Exception:
			frappe.log_error(
				title=f"Notification failed: {fn.__name__}", message=frappe.get_traceback()
			)
			return False

	return wrapper


def _send(to: str, subject: str, body: str):
	"""One mail, now rather than queued.

	`now=True` on purpose: a queued mail is handed to a background worker and
	the caller learns nothing about whether it will ever be delivered. Every
	send here is either telling somebody their workspace is ready or telling
	them it is about to be switched off, and both are worth a failure the caller
	can see.

	Refuses outright when the site has no way to send. Frappe queues a mail with
	no outgoing account without complaining, so without this a control plane
	that was never given an Email Account would report every notification as
	sent and deliver none of them.
	"""
	if not outgoing_configured():
		raise RuntimeError(
			"This site has no default outgoing Email Account, so nothing can be "
			"sent. Nobody is being told their workspace is suspended, archived "
			"or about to be deleted."
		)

	if not to:
		raise RuntimeError("No recipient.")

	frappe.sendmail(recipients=[to], subject=subject, message=body, now=True)


def outgoing_configured() -> bool:
	"""Whether this site can send mail at all.

	Read on every send rather than cached: an operator fixing this mid-incident
	should not have to wait out a cache to find out whether it worked.
	"""
	return bool(
		frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1})
	)


@_safe
def workspace_ready(tenant_name: str, password_link: str | None = None):
	"""Your workspace is ready, with the link."""
	tenant = frappe.get_doc("Tenant", tenant_name)
	url = f"https://{tenant.primary_domain or tenant.site_name}"

	sign_in = (
		f'<p><a href="{password_link}">Set your password</a> to sign in.</p>'
		if password_link
		else "<p>Sign in with the account you used at checkout.</p>"
	)

	_send(
		tenant.owner_email,
		f"{tenant.tenant_name} is ready",
		f"""
		<p>Your workspace is live at <a href="{url}">{url}</a>.</p>
		{sign_in}
		<p>You can add your own domain and manage billing from your account
		   at any time.</p>
		""",
	)


@_safe
def workspace_building(request_name: str):
	"""Sent when no warm site was waiting and the build will take minutes.

	Its whole job is to let someone close the tab, so it says plainly that
	nothing more is required of them.
	"""
	request = frappe.get_doc("Account Request", request_name)
	_send(
		request.email,
		f"Setting up {request.workspace_name}",
		"""
		<p>Your payment went through and we are building your workspace now.
		   It usually takes a few minutes.</p>
		<p>There is nothing else for you to do — we will email you the link the
		   moment it is ready. You can close this tab.</p>
		""",
	)


@_safe
def provisioning_failed(request_name: str):
	"""Sent when fulfilment stopped after payment.

	Says what happened without pretending it is the customer's problem to fix,
	because it is not.
	"""
	request = frappe.get_doc("Account Request", request_name)
	_send(
		request.email,
		f"We hit a problem setting up {request.workspace_name}",
		"""
		<p>Your payment went through, but something went wrong while building
		   your workspace.</p>
		<p>We have been alerted and are looking at it. You do not need to do
		   anything, and you will not be charged again.</p>
		""",
	)


@_safe
def quota_warning(tenant_name: str, resource: str, fraction: float):
	"""Sent once as a workspace approaches a limit.

	Early enough to act on: at the hard limit the next upload simply fails, and
	discovering that mid-work is the experience this exists to prevent.
	"""
	tenant = frappe.get_doc("Tenant", tenant_name)
	label = {"storage": "file storage", "database": "database", "users": "user seats"}[resource]

	_send(
		tenant.owner_email,
		f"{tenant.tenant_name} is running low on {label}",
		f"""
		<p>{tenant.tenant_name} has used {int(fraction * 100)}% of its {label}.</p>
		<p>At 100% new {'uploads' if resource != 'users' else 'invitations'} stop
		   until there is room. You can free some up or add more from your
		   account.</p>
		""",
	)


@_safe
def domain_verified(tenant_name: str, domain: str):
	tenant = frappe.get_doc("Tenant", tenant_name)
	_send(
		tenant.owner_email,
		f"{domain} is now live",
		f'<p>{tenant.tenant_name} is now reachable at <a href="https://{domain}">{domain}</a>.</p>',
	)


# --------------------------------------------------------------------------- #
# The lifecycle ladder
# --------------------------------------------------------------------------- #
# Six emails, and they are the only warning anybody gets before a workspace is
# switched off and eventually destroyed. Two rules run through all of them:
#
# * **Always name the date.** "Soon" and "shortly" are what make somebody put an
#   email aside. Every one of these says the day.
# * **Never imply the data is already gone when it is not.** Suspended is not
#   archived and archived is not purged, and somebody reading in a hurry will
#   act on whichever they think it is.

def _workspace(tenant_name: str):
	return frappe.get_doc("Tenant", tenant_name)


def _account_link() -> str:
	url = frappe.db.get_single_value("OneSpace Control Settings", "control_plane_url") or ""
	return f"{url.rstrip('/')}/one" if url else ""


def _billing_line() -> str:
	link = _account_link()
	if not link:
		return "<p>Update your card from your account area.</p>"
	return f'<p><a href="{link}">Update your card</a> to put this right.</p>'


@_safe
def payment_failed(tenant_name: str, suspends_on: str):
	"""The first one. The workspace is still working and nothing has happened yet."""
	tenant = _workspace(tenant_name)
	_send(
		tenant.owner_email,
		f"We could not take payment for {tenant.tenant_name}",
		f"""
		<p>The last payment for {tenant.tenant_name} did not go through. Your
		   card issuer may have declined it, or the card may have expired.</p>
		<p><strong>Nothing has changed yet.</strong> Your workspace is working
		   normally, and we will keep trying the card. If it has not gone
		   through by <strong>{suspends_on}</strong>, the workspace will be
		   switched off until it does.</p>
		{_billing_line()}
		""",
	)


@_safe
def suspension_warning(tenant_name: str, suspends_on: str):
	"""The second. Close enough to act on, far enough to still have time."""
	tenant = _workspace(tenant_name)
	_send(
		tenant.owner_email,
		f"{tenant.tenant_name} will be switched off on {suspends_on}",
		f"""
		<p>We still have not been able to take payment for
		   {tenant.tenant_name}.</p>
		<p>On <strong>{suspends_on}</strong> the workspace will be switched off.
		   Nothing is deleted — your data stays exactly as it is, and paying
		   brings it back within a minute.</p>
		{_billing_line()}
		""",
	)


@_safe
def suspended(tenant_name: str, archives_on: str, has_copy: bool = True):
	"""It is off. Say plainly that the data is still there."""
	tenant = _workspace(tenant_name)
	_send(
		tenant.owner_email,
		f"{tenant.tenant_name} has been switched off",
		f"""
		<p>{tenant.tenant_name} is switched off because the subscription is
		   unpaid. Nobody can sign in to it at the moment.</p>
		<p><strong>Your data has not been touched.</strong> Paying brings the
		   workspace back within a minute, exactly as you left it.</p>
		<p>If it is still unpaid on <strong>{archives_on}</strong> we will remove
		   the running site and keep a copy of everything instead. Bringing it
		   back from there takes a few minutes rather than a minute, and we will
		   write to you again before anything is deleted for good.</p>
		{_billing_line()}
		""",
	)


@_safe
def archived(tenant_name: str, purge_after: str):
	"""The site is gone. The copy is not, and the date it goes is the point."""
	tenant = _workspace(tenant_name)
	_send(
		tenant.owner_email,
		f"{tenant.tenant_name} has been archived",
		f"""
		<p>{tenant.tenant_name} has been unpaid long enough that we have removed
		   the running site.</p>
		<p><strong>We are holding a complete copy of it</strong> — your database,
		   your files and your settings — until
		   <strong>{purge_after}</strong>. Paying before then restores the whole
		   workspace; it takes a few minutes rather than being instant.</p>
		<p>After {purge_after} the copy and every file we hold for you are
		   deleted permanently. We will write to you again before that happens.</p>
		{_billing_line()}
		""",
	)


@_safe
def purge_warning(tenant_name: str, purge_after: str):
	"""The last chance. Nothing after this is recoverable."""
	tenant = _workspace(tenant_name)
	_send(
		tenant.owner_email,
		f"Last chance: {tenant.tenant_name} is deleted on {purge_after}",
		f"""
		<p>On <strong>{purge_after}</strong> we permanently delete everything we
		   hold for {tenant.tenant_name}: the database, every file, and every
		   backup.</p>
		<p><strong>This cannot be undone</strong>, and after that date we will
		   not be able to recover your workspace even if you ask us to.</p>
		<p>Paying before {purge_after} restores it in full.</p>
		{_billing_line()}
		""",
	)


@_safe
def purged(tenant_name: str):
	"""After the fact. Short, and it does not pretend anything can be done."""
	tenant = _workspace(tenant_name)
	_send(
		tenant.owner_email,
		f"{tenant.tenant_name} has been deleted",
		f"""
		<p>Everything we held for {tenant.tenant_name} has now been deleted, as
		   we said it would be.</p>
		<p>There is nothing left to restore. You are welcome to start a new
		   workspace at any time, and it will begin empty.</p>
		""",
	)


@_safe
def restored(tenant_name: str):
	tenant = _workspace(tenant_name)
	url = f"https://{tenant.primary_domain or tenant.site_name}"
	_send(
		tenant.owner_email,
		f"{tenant.tenant_name} is back",
		f"""
		<p>Thank you — your payment went through and
		   {tenant.tenant_name} has been restored from the copy we were
		   holding.</p>
		<p>It is live again at <a href="{url}">{url}</a>, with your data as it
		   was when the workspace was archived.</p>
		""",
	)


@_safe
def nothing_to_restore(tenant_name: str):
	"""Paid, but there is no copy left. Says so rather than quietly doing nothing."""
	tenant = _workspace(tenant_name)
	_send(
		tenant.owner_email,
		f"About {tenant.tenant_name}",
		f"""
		<p>Your payment went through, but we are no longer holding a copy of
		   {tenant.tenant_name} — it was deleted after the retention period we
		   wrote to you about.</p>
		<p>We have not charged you for a workspace we cannot bring back. Please
		   reply to this email and we will sort out either a new workspace or a
		   refund, whichever you would prefer.</p>
		""",
	)


@_safe
def over_quota(tenant_name: str, resources: list[str], grace_until: str):
	"""Sent the moment a workspace ends up holding more than it is allowed.

	Distinct from `quota_warning`, which fires at 80% of a limit they are walking
	towards. This one usually fires because the limit came *down* — an add-on
	line left the subscription — so it leads with that rather than telling
	somebody they have used too much, which from where they are sitting is not
	what happened.
	"""
	tenant = _workspace(tenant_name)
	labels = {"storage": "file storage", "database": "database", "users": "user seats"}
	named = ", ".join(labels.get(r, r) for r in resources)

	_send(
		tenant.owner_email,
		f"{tenant.tenant_name} is over its {named} limit",
		f"""
		<p>{tenant.tenant_name} is currently holding more {named} than its plan
		   and add-ons allow. This often happens because an add-on stopped being
		   billed rather than because anything in the workspace changed.</p>
		<p><strong>Nothing is blocked and nothing has been deleted.</strong> You
		   have until <strong>{grace_until}</strong> to either add the storage
		   back or free some up. Until then the workspace works normally, except
		   that it cannot grow past where it is now.</p>
		<p>After {grace_until}, new uploads stop until there is room again.</p>
		{_billing_line()}
		""",
	)
