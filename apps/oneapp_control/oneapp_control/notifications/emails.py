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
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except Exception:
			frappe.log_error(
				title=f"Notification failed: {fn.__name__}", message=frappe.get_traceback()
			)
			return None

	return wrapper


def _send(to: str, subject: str, body: str):
	frappe.sendmail(recipients=[to], subject=subject, message=body, now=True)


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
