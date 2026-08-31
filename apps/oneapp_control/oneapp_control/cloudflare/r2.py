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
	s = frappe.get_single("OneSpace Control Settings")
	return {
		"account_id": s.r2_account_id,
		"token": s.get_password("r2_admin_token", raise_exception=False),
		"public_base": s.r2_public_base,
	}


def is_configured() -> bool:
	c = config()
	return bool(c["account_id"] and c["token"])


def has_client() -> bool:
	"""Whether the object half of this module can run at all.

	Separate from `is_configured`, which is about the Cloudflare admin token and
	governs bucket creation. Retention, promotion to cold storage and the purge
	all go through boto3 instead, and a control plane without it would report
	every sweep as having found nothing to do.
	"""
	try:
		import boto3  # noqa: F401
	except ImportError:
		return False
	return True


def _request(method: str, path: str, jurisdiction: str | None = None, **kwargs):
	c = config()
	if not is_configured():
		raise R2NotConfigured("R2 admin credentials are not set in OneSpace Control Settings.")

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


# --------------------------------------------------------------------------- #
# Objects
# --------------------------------------------------------------------------- #
# Everything above talks to the Cloudflare API, which administers *buckets*. It
# cannot see an object. The lifecycle needs to: promote a backup to cold storage,
# hand press a download URL to restore from, expire a workspace's old copies, and
# eventually delete everything it owns.
#
# So there is a second client here, over R2's S3-compatible endpoint, using the
# same access keys the tenant sites hold. Deliberately on the control plane and
# not on the tenant: retention has to run for a workspace whose site is
# suspended, and a purge must not depend on the thing being purged.

# S3 caps a page at 1,000 keys, and both list and delete-batch inherit it.
PAGE = 1000


def s3():
	"""boto3 against R2's S3 endpoint.

	Imported inside the function, like the tenant side does it, so a control
	plane without boto3 fails on the one call that needs it rather than at
	import and taking the whole app with it.
	"""
	import boto3
	from botocore.config import Config

	c = config()
	if not is_configured():
		raise R2NotConfigured("R2 admin credentials are not set in OneSpace Control Settings.")

	settings = frappe.get_single("OneSpace Control Settings")
	access_key = settings.r2_access_key
	secret_key = settings.get_password("r2_secret_key", raise_exception=False)
	if not (access_key and secret_key):
		raise R2NotConfigured(
			"R2 access keys are not set. The admin token administers buckets; "
			"reading and writing objects needs the S3 keys."
		)

	return boto3.client(
		"s3",
		endpoint_url=f"https://{c['account_id']}.r2.cloudflarestorage.com",
		aws_access_key_id=access_key,
		aws_secret_access_key=secret_key,
		# R2 ignores the region but the SDK insists on one.
		region_name="auto",
		config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
	)


def objects(bucket: str, prefix: str) -> list[dict]:
	"""Every object under a prefix, paginated. Newest last.

	Returns `{"key", "size", "modified"}`. The whole listing rather than a
	generator: a caller deciding what to delete has to see the set before it
	deletes any of it, and a tenant's prefix is thousands of keys at worst.
	"""
	found = []
	token = None
	client = s3()

	while True:
		kwargs = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": PAGE}
		if token:
			kwargs["ContinuationToken"] = token

		page = client.list_objects_v2(**kwargs)
		for row in page.get("Contents") or []:
			found.append(
				{
					"key": row["Key"],
					"size": int(row.get("Size") or 0),
					"modified": row.get("LastModified"),
				}
			)

		if not page.get("IsTruncated"):
			break
		token = page.get("NextContinuationToken")
		if not token:
			break

	found.sort(key=lambda row: (row["modified"] is None, row["modified"]))
	return found


def prefix_bytes(bucket: str, prefix: str) -> int:
	return sum(row["size"] for row in objects(bucket, prefix))


def copy(bucket: str, source_key: str, target_key: str) -> None:
	"""Server-side copy. The bytes never travel through us.

	Which is the whole reason cold storage is a copy rather than a re-upload:
	promoting a 4 GB backup costs a request, not four gigabytes of transfer on
	a control plane that has no business moving them.
	"""
	s3().copy_object(
		Bucket=bucket,
		CopySource={"Bucket": bucket, "Key": source_key},
		Key=target_key,
	)


def put(bucket: str, key: str, body: bytes, content_type: str = "application/json") -> None:
	s3().put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)


def get(bucket: str, key: str) -> bytes | None:
	"""One object's bytes, or None if it is not there.

	For the manifest and nothing larger — anything big is presigned and handed
	to whoever actually needs the bytes.
	"""
	try:
		return s3().get_object(Bucket=bucket, Key=key)["Body"].read()
	except Exception:
		return None


def delete_keys(bucket: str, keys: list[str]) -> int:
	"""Delete an explicit list. Returns how many R2 confirmed.

	Explicit rather than by prefix, because the caller has already decided what
	may go — a delete that takes its own argument from a listing it did not
	inspect is how a retention sweep eats a cold copy.
	"""
	if not keys:
		return 0

	client = s3()
	deleted = 0

	for start in range(0, len(keys), PAGE):
		batch = keys[start : start + PAGE]
		result = client.delete_objects(
			Bucket=bucket, Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True}
		)
		errors = result.get("Errors") or []
		if errors:
			frappe.log_error(
				title="R2 delete refused some keys",
				message="\n".join(
					f"{e.get('Key')}: {e.get('Code')} {e.get('Message')}" for e in errors[:50]
				),
			)
		deleted += len(batch) - len(errors)

	return deleted


def delete_prefix(bucket: str, prefix: str) -> int:
	"""Everything under a prefix. Returns how many objects went.

	Refuses an empty or bare prefix outright. `delete_prefix(bucket, "")` would
	empty the bucket for every tenant in it, and the shape of this function is
	such that one missing f-string argument produces exactly that call.
	"""
	prefix = (prefix or "").strip()
	if not prefix or prefix == "/" or "/" not in prefix.rstrip("/"):
		raise R2Error(
			f"Refusing to delete by the prefix {prefix!r}: it is not scoped to "
			"anything. A prefix has to name a tenant."
		)

	return delete_keys(bucket, [row["key"] for row in objects(bucket, prefix)])


def presign(bucket: str, key: str, ttl: int = 3600) -> str:
	"""A time-limited download URL.

	An hour by default, which is what a restore needs: press fetches the files
	itself and a database dump of any size takes longer than the five minutes
	an attachment redirect is given.
	"""
	return s3().generate_presigned_url(
		"get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=ttl
	)
