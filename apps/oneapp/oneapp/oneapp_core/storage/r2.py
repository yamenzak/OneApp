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
from frappe.utils import get_url

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
	"""Whether this site can actually put an object in R2.

	The keys *and* the client library, because they fail differently and only
	one of them is visible. Keys missing is a site that has not been given
	storage yet and correctly falls back to local disk. boto3 missing is a site
	that thinks it has storage and raises `ImportError` on every upload — and
	since `File.after_insert` swallows exceptions so an upload never fails
	outright, that lands as attachments that quietly are not there.
	"""
	c = config()
	if not all([c["account_id"], c["bucket"], c["access_key"], c["secret_key"]]):
		return False
	return has_client()


def has_client() -> bool:
	try:
		import boto3  # noqa: F401
	except ImportError:
		return False
	return True


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


# --------------------------------------------------------------------------- #
# CORS
# --------------------------------------------------------------------------- #

#: The bucket must allow the browser to PUT at it and, crucially, must *expose*
#: `ETag`. A multipart upload is completed by sending back each part's ETag, and
#: a response header the browser cannot read does not exist as far as JavaScript
#: is concerned — so without this line every direct upload uploads every byte
#: correctly and then fails on the last call, which is the most expensive way a
#: missing config line can fail.
CORS_EXPOSE = ["ETag"]
CORS_METHODS = ["GET", "PUT", "HEAD"]


def cors_rules(origins: list[str]) -> list[dict]:
	return [
		{
			"AllowedOrigins": origins,
			"AllowedMethods": CORS_METHODS,
			"AllowedHeaders": ["*"],
			"ExposeHeaders": CORS_EXPOSE,
			"MaxAgeSeconds": 3600,
		}
	]


def ensure_cors(origins: list[str] | None = None) -> dict:
	"""Put the CORS policy the browser needs onto the bucket.

	Idempotent, and safe to run from `bench execute`. Called by hand rather than
	on a schedule: the bucket is shared by every tenant on a shard, so this is a
	bucket-level operation and not a per-site one — see `docs/ONEADMIN.md`.
	"""
	if not is_configured():
		raise R2NotConfigured("R2 keys are missing from site_config.json.")

	origins = origins or [get_url()]
	rules = cors_rules(origins)
	client().put_bucket_cors(
		Bucket=config()["bucket"], CORSConfiguration={"CORSRules": rules}
	)
	return {"ok": True, "origins": origins}


def guess_content_type(filename: str) -> str:
	import mimetypes

	return mimetypes.guess_type(filename or "")[0] or "application/octet-stream"


# --------------------------------------------------------------------------- #
# Download route
# --------------------------------------------------------------------------- #

@frappe.whitelist()
def download(file: str):
	"""Serve a private file after checking the reader may have it.

	The permission check is the whole point: without it, a presigned URL endpoint
	is an open door to every file in the bucket.

	The check is Frappe's own and not ours. `File.has_permission` is a hook the
	framework registers, and it already answers all four cases — a public file,
	the owner, a `DocShare`, and delegation to the document the file hangs off.
	This used to hand-roll three of those and miss the share, which was fine
	while every file was an attachment and became a bug the moment the Drive
	gave a file a life of its own: a folder somebody shared with a colleague
	opened for them and every file in it refused to download.
	"""
	doc = frappe.get_doc("File", file)

	if not frappe.has_permission("File", "read", doc=doc):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	serve(doc)


def serve(doc):
	"""Hand over one file's bytes, from wherever this site keeps them.

	Two places, because a site with no R2 keys is a real configuration and not a
	broken one — development runs that way, and so does anybody self-hosting
	before they have a bucket. There the object is on local disk and there is
	nothing to presign, so the response carries the content.

	Nothing here checks a permission. Every caller has already checked one, and
	they check different ones: the download route asks whether the reader may
	read the file, and a share link asks nothing at all because the secret in the
	URL was the whole of the authentication.
	"""
	# A sheet has no object anywhere. Its bytes are produced on the way out —
	# see `sheets/export.py` — and asking `get_content()` for them answered 500
	# on every download of a sheet and every share link to one.
	if doc.get("custom_kind") == "Sheet":
		from oneapp.oneapp_core.sheets import export

		export.to_response(doc)
		return

	# `is_configured()` and not "does this row have a key". A key is where the
	# object *would* be; presigning it needs the client and the credentials, and
	# a site that has the row but not the keys cannot serve from R2 at all. A
	# row keeps its key through a site being reconfigured, so the two questions
	# come apart in practice.
	if is_configured():
		# Built before anything is assigned. `presigned_url` can raise, and
		# setting the type first leaves a half-made redirect behind — which
		# Werkzeug then answers as `Location: None`, a 500 that says nothing
		# about what actually failed.
		location = presigned_url(doc.get("r2_key") or object_key(doc))
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = location
		return

	frappe.local.response.filename = doc.file_name
	frappe.local.response.filecontent = doc.get_content()
	frappe.local.response.type = "download"


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
