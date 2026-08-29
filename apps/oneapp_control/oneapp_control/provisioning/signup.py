"""Turning a paid Account Request into a working workspace.

Everything here runs after money has changed hands, which sets the failure
policy: never leave the customer with a charge and nothing to show for it. Each
step records where it got to, and a failure marks the request Failed with a
reason rather than unwinding — an operator can resume it, and the customer can
be told something true.
"""

import secrets

import frappe
from frappe import _
from frappe.utils import now_datetime

from oneapp_control.utils.slug import is_available

CUSTOMER_ROLE = "OneApp Customer"


def fulfil(request_name: str):
	"""Create the owner account and the tenant, then start provisioning."""
	request = frappe.get_doc("Account Request", request_name)

	try:
		user = ensure_owner_user(request)
		tenant = ensure_tenant(request, user)
		request.db_set("status", "Provisioning")
		start_provisioning(tenant)
	except Exception as e:
		# The customer has paid. Record why this stopped rather than rolling back
		# to a state that looks like nothing happened.
		request.db_set("status", "Failed")
		request.db_set("failure_reason", str(e)[:500])
		frappe.log_error(
			title=f"Signup fulfilment failed for {request_name}",
			message=frappe.get_traceback(),
		)
		raise


def ensure_owner_user(request) -> str:
	"""The customer's control-plane account.

	They land here for billing and workspace settings, so the account exists on
	the control plane rather than only inside their site. It gets the customer
	role and nothing else — every customer endpoint scopes to the tenant this
	user owns.
	"""
	if request.user and frappe.db.exists("User", request.user):
		return request.user

	ensure_customer_role()

	if frappe.db.exists("User", request.email):
		user = frappe.get_doc("User", request.email)
	else:
		first, _sep, last = (request.workspace_name or "").partition(" ")
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": request.email,
				"first_name": first or request.email.split("@")[0],
				"last_name": last or "",
				"send_welcome_email": 0,
				"user_type": "Website User",
			}
		).insert(ignore_permissions=True)

	if not any(r.role == CUSTOMER_ROLE for r in user.roles):
		user.append("roles", {"role": CUSTOMER_ROLE})
		user.save(ignore_permissions=True)

	request.db_set("user", user.name)
	return user.name


def ensure_customer_role():
	if frappe.db.exists("Role", CUSTOMER_ROLE):
		return
	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": CUSTOMER_ROLE,
			# Portal only. A customer must never reach the desk on the control
			# plane, where every other tenant's data lives.
			"desk_access": 0,
		}
	).insert(ignore_permissions=True)


def ensure_tenant(request, user: str):
	"""Create the tenant, re-checking the slug.

	It was validated when the form was submitted, but that may have been a while
	ago and someone else may have taken it in between.
	"""
	if request.tenant and frappe.db.exists("Tenant", request.tenant):
		return frappe.get_doc("Tenant", request.tenant)

	slug = request.requested_slug
	if not is_available(slug):
		slug = derive_alternative(slug)

	tenant = frappe.get_doc(
		{
			"doctype": "Tenant",
			"tenant_slug": slug,
			"tenant_name": request.workspace_name,
			"owner_email": request.email,
			"owner_user": user,
			"plan": request.plan,
			"status": "Draft",
		}
	).insert(ignore_permissions=True)

	request.db_set("tenant", tenant.name)

	if request.stripe_subscription_id:
		from oneapp_control.billing.webhooks import ensure_subscription

		subscription = ensure_subscription(
			tenant=tenant.name,
			stripe_subscription_id=request.stripe_subscription_id,
			stripe_customer_id=request.stripe_customer_id,
			plan=request.plan,
			interval=request.interval,
		)
		tenant.db_set("subscription", subscription.name)

	return tenant


def derive_alternative(slug: str) -> str:
	"""Someone paid for this workspace; give them a usable name rather than an
	error."""
	for _attempt in range(10):
		candidate = f"{slug}-{secrets.token_hex(2)}"
		if is_available(candidate):
			return candidate
	frappe.throw(_("Could not find an available subdomain for '{0}'.").format(slug))


def start_provisioning(tenant):
	"""Claim a warm site if one is waiting, otherwise build from scratch."""
	from oneapp_control.provisioning import runner, standby

	claimed = standby.claim(tenant.name)
	if claimed:
		return claimed

	tenant.db_set("status", "Provisioning")
	return runner.provision_tenant(tenant.name)


def complete(tenant_name: str):
	"""Called when a tenant reaches Active. Closes out the request and invites
	the owner."""
	request_name = frappe.db.get_value("Account Request", {"tenant": tenant_name}, "name")
	if not request_name:
		return

	request = frappe.get_doc("Account Request", request_name)
	if request.status == "Completed":
		return

	request.db_set("status", "Completed")
	request.db_set("completed_on", now_datetime())

	send_owner_invite(request)


def send_owner_invite(request):
	"""One email, with the link and a way to set a password.

	Best-effort: the workspace is live either way, and the customer can always
	reset their password. Failing the fulfilment over an email would be worse.
	"""
	try:
		site = frappe.db.get_value("Tenant", request.tenant, "site_name")
		user = frappe.get_doc("User", request.user)
		key = user.reset_password()

		frappe.sendmail(
			recipients=[request.email],
			subject=f"{request.workspace_name} is ready",
			message=(
				f"<p>Your workspace is ready at "
				f'<a href="https://{site}">{site}</a>.</p>'
				f'<p><a href="{frappe.utils.get_url()}/update-password?key={key}">'
				f"Set your password</a> to sign in.</p>"
			),
			now=True,
		)
	except Exception:
		frappe.log_error(
			title=f"Owner invite failed for {request.name}", message=frappe.get_traceback()
		)
