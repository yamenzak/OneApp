"""R2 buckets, created and rotated through the Cloudflare API.

Objects are never pooled into one enormous bucket. A single bucket holding every
tenant's files is one credential, one misconfiguration and one bad lifecycle rule
away from losing everything at once — so buckets are capped, and a fresh one is
created when a cap is reached. The worst case stays bounded.

Jurisdiction is chosen by the customer at signup. R2 pins an EU bucket to EU data
centres, which is what "where is my data" actually needs answering, and it cannot
be changed afterwards without moving objects.
"""

import frappe
from frappe import _
import requests
from frappe.utils import now_datetime

API_BASE = "https://api.cloudflare.com/client/v4"
TIMEOUT = 30

# R2's own name for the EU jurisdiction. Global buckets pass no location hint.
JURISDICTION_HEADER = "cf-r2-jurisdiction"
EU = "eu"


class R2Error(Exception):
	pass


class R2NotConfigured(R2Error):
	pass


def config() -> dict:
	s = frappe.get_single("OneApp Control Settings")
	return {
		"account_id": s.r2_account_id,
		"token": s.get_password("r2_admin_token", raise_exception=False),
		"public_base": s.r2_public_base,
	}


def is_configured() -> bool:
	c = config()
	return bool(c["account_id"] and c["token"])


def _request(method: str, path: str, jurisdiction: str | None = None, **kwargs):
	c = config()
	if not is_configured():
		raise R2NotConfigured("R2 admin credentials are not set in OneApp Control Settings.")

	headers = {"Authorization": f"Bearer {c['token']}"}
	if jurisdiction == EU:
		headers[JURISDICTION_HEADER] = EU

	try:
		response = requests.request(
			method,
			f"{API_BASE}/accounts/{c['account_id']}/r2/{path.lstrip('/')}",
			headers=headers,
			timeout=TIMEOUT,
			**kwargs,
		)
	except requests.RequestException as e:
		raise R2Error(f"Cloudflare R2 unreachable: {e}") from e

	body = {}
	try:
		body = response.json()
	except ValueError:
		pass

	if response.status_code >= 400 or not body.get("success", True):
		raise R2Error(
			f"Cloudflare R2 {response.status_code}: {body.get('errors') or response.text[:300]}"
		)

	return body


def create_bucket(name: str, jurisdiction: str = "Global") -> dict:
	juris = EU if jurisdiction == "EU" else None
	payload = {"name": name}
	if juris:
		payload["locationHint"] = "weur"

	_request("POST", "buckets", jurisdiction=juris, json=payload)
	return {"name": name, "jurisdiction": jurisdiction}


# --------------------------------------------------------------------------- #
# Allocation
# --------------------------------------------------------------------------- #

def allocate(jurisdiction: str = "Global") -> str:
	"""A bucket with headroom in this jurisdiction, creating one if needed.

	Called at provisioning. A tenant keeps its bucket for life — moving objects
	between buckets later is a migration, not a setting.
	"""
	existing = frappe.get_all(
		"Storage Bucket",
		filters={"jurisdiction": jurisdiction, "status": "Active"},
		fields=["name", "tenant_count", "max_tenants", "bytes_used", "max_bytes"],
		order_by="tenant_count desc",
	)

	# Fill the fullest bucket that still has room rather than spreading evenly:
	# fewer part-full buckets is easier to reason about and to retire.
	for bucket in existing:
		if _has_headroom(bucket):
			return bucket["name"]

	return provision_bucket(jurisdiction)


def _has_headroom(bucket) -> bool:
	if bucket["max_tenants"] and bucket["tenant_count"] >= bucket["max_tenants"]:
		return False
	if bucket["max_bytes"] and (bucket["bytes_used"] or 0) >= bucket["max_bytes"]:
		return False
	return True


def provision_bucket(jurisdiction: str = "Global") -> str:
	"""Create the next bucket in a jurisdiction and record it."""
	import secrets

	suffix = "eu" if jurisdiction == "EU" else "gl"
	name = f"oneapp-{suffix}-{secrets.token_hex(3)}"

	doc = frappe.get_doc(
		{
			"doctype": "Storage Bucket",
			"bucket_name": name,
			"jurisdiction": jurisdiction,
			"status": "Provisioning",
			"created_on": now_datetime(),
		}
	).insert(ignore_permissions=True)

	try:
		create_bucket(name, jurisdiction)
	except R2Error as e:
		doc.db_set("status", "Retired")
		doc.db_set("last_error", str(e)[:500])
		raise

	doc.db_set("status", "Active")
	if config()["public_base"]:
		doc.db_set("public_base_url", config()["public_base"])

	return doc.name


def assign(tenant_name: str) -> str:
	"""Give a tenant its bucket, rotating the pool when one fills."""
	tenant = frappe.get_doc("Tenant", tenant_name)
	if tenant.storage_bucket:
		return tenant.storage_bucket

	bucket = allocate(tenant.storage_jurisdiction or "Global")
	tenant.db_set("storage_bucket", bucket)

	count = frappe.db.count("Tenant", {"storage_bucket": bucket})
	frappe.db.set_value("Storage Bucket", bucket, "tenant_count", count)

	# Close the bucket as soon as it is full so the next signup does not race
	# into it.
	doc = frappe.get_doc("Storage Bucket", bucket)
	if doc.max_tenants and count >= doc.max_tenants:
		doc.db_set("status", "Full")

	return bucket


def refresh_usage():
	"""Scheduled. Roll tenant usage up per bucket and retire full ones."""
	for bucket in frappe.get_all("Storage Bucket", pluck="name"):
		rows = frappe.db.sql(
			"""
			SELECT COUNT(*), COALESCE(SUM(storage_used_bytes), 0)
			FROM `tabTenant` WHERE storage_bucket = %s AND status != 'Archived'
			""",
			bucket,
		)[0]
		frappe.db.set_value(
			"Storage Bucket", bucket, {"tenant_count": rows[0], "bytes_used": rows[1]},
			update_modified=False,
		)

	frappe.db.commit()


@frappe.whitelist()
def bucket_report() -> list[dict]:
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	rows = frappe.get_all(
		"Storage Bucket",
		fields=["name", "jurisdiction", "status", "tenant_count", "max_tenants", "bytes_used"],
		order_by="jurisdiction asc, creation asc",
	)
	for row in rows:
		cap = row["max_tenants"] or 0
		row["utilisation"] = round(row["tenant_count"] / cap, 3) if cap else None
	return rows
