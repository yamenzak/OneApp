"""Cloudflare R2 object storage.

Frappe has no native object storage for attachments, so this replaces the
filesystem for user files. Two paths, deliberately different:

* **Private files** go through our own route, which runs Frappe's permission
  check against the attached document and only then redirects to a short-lived
  presigned URL. The object is never publicly reachable.
* **Public files** are served straight from `cdn.4dl.app`, which is where the
  actual bandwidth goes and the reason the app origin stays cheap.

Objects are keyed by tenant so a bucket listing is legible and a tenant export
is a prefix copy.
"""

import os

import frappe
from frappe import _

PRESIGN_TTL = 300


class R2NotConfigured(Exception):
	pass


def config() -> dict:
	conf = frappe.conf
	return {
		"account_id": conf.get("oneapp_r2_account_id"),
		"bucket": conf.get("oneapp_r2_bucket"),
		"access_key": conf.get("oneapp_r2_access_key"),
		"secret_key": conf.get("oneapp_r2_secret_key"),
		"public_base": (conf.get("oneapp_r2_public_base") or "").rstrip("/"),
		"tenant": conf.get("oneapp_tenant") or "unknown",
	}


def is_configured() -> bool:
	c = config()
	return all([c["account_id"], c["bucket"], c["access_key"], c["secret_key"]])


def client():
	"""boto3 against R2's S3-compatible endpoint."""
	import boto3
	from botocore.config import Config

	c = config()
	if not is_configured():
		raise R2NotConfigured("R2 keys are missing from site_config.json.")

	return boto3.client(
		"s3",
		endpoint_url=f"https://{c['account_id']}.r2.cloudflarestorage.com",
		aws_access_key_id=c["access_key"],
		aws_secret_access_key=c["secret_key"],
		# R2 ignores regions but the SDK insists on one.
		region_name="auto",
		config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
	)


def object_key(file_doc) -> str:
	c = config()
	scope = "private" if file_doc.is_private else "public"
	return f"tenants/{c['tenant']}/{scope}/{file_doc.name}/{file_doc.file_name}"


# --------------------------------------------------------------------------- #
# Upload / delete
# --------------------------------------------------------------------------- #

def upload(file_doc, content: bytes) -> str:
	"""Put an object and return the URL to store on the File document."""
	c = config()
	key = object_key(file_doc)

	client().put_object(
		Bucket=c["bucket"],
		Key=key,
		Body=content,
		ContentType=guess_content_type(file_doc.file_name),
	)

	if file_doc.is_private:
		# Routed through us so permissions are checked on every access.
		return f"/api/method/oneapp.oneapp_core.storage.r2.download?file={file_doc.name}"

	if c["public_base"]:
		return f"{c['public_base']}/{key}"

	return f"/api/method/oneapp.oneapp_core.storage.r2.download?file={file_doc.name}"


def delete(key: str):
	try:
		client().delete_object(Bucket=config()["bucket"], Key=key)
	except Exception:
		# A failed delete leaves an orphan object, which costs pennies. Failing the
		# user's delete because cleanup failed would be worse.
		frappe.log_error(title="R2 delete failed", message=frappe.get_traceback())


def presigned_url(key: str, ttl: int = PRESIGN_TTL) -> str:
	return client().generate_presigned_url(
		"get_object",
		Params={"Bucket": config()["bucket"], "Key": key},
		ExpiresIn=ttl,
	)


def guess_content_type(filename: str) -> str:
	import mimetypes

	return mimetypes.guess_type(filename or "")[0] or "application/octet-stream"


# --------------------------------------------------------------------------- #
# Download route
# --------------------------------------------------------------------------- #

@frappe.whitelist()
def download(file: str):
	"""Serve a private file after checking permission on its attached document.

	The permission check is the whole point: without it, a presigned URL endpoint
	is an open door to every file in the bucket.
	"""
	doc = frappe.get_doc("File", file)

	if doc.is_private:
		# Frappe's own rule: access follows the document the file is attached to.
		if doc.attached_to_doctype and doc.attached_to_name:
			if not frappe.has_permission(
				doc.attached_to_doctype, "read", doc.attached_to_name
			):
				frappe.throw(_("Not permitted."), frappe.PermissionError)
		elif doc.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
			frappe.throw(_("Not permitted."), frappe.PermissionError)

	key = doc.get("r2_key") or object_key(doc)

	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = presigned_url(key)


# --------------------------------------------------------------------------- #
# Backups
# --------------------------------------------------------------------------- #

def sync_backup_to_r2(file_path: str, prefix: str = "backups") -> str | None:
	"""Second custodian for backups, alongside Frappe Cloud's own.

	One provider holding both your site and your only backup of it is not a
	backup strategy.
	"""
	if not is_configured() or not os.path.exists(file_path):
		return None

	c = config()
	key = f"{prefix}/{c['tenant']}/{os.path.basename(file_path)}"

	with open(file_path, "rb") as fh:
		client().put_object(Bucket=c["bucket"], Key=key, Body=fh)

	return key
