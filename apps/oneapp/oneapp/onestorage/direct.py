"""Large files go to R2 without passing through Python.

Every upload before this was one `multipart/form-data` POST to Frappe, which
read the whole body into memory, wrote it to disk, inserted a `File`, read it
back and pushed it to R2. That is four copies of the bytes and one blocking
worker, and for anything the size of a site video it does not merely go slowly
— it fails, on whichever of the request-body limit, the gunicorn timeout or the
proxy's own ceiling it meets first.

So the bytes never come here. The browser asks for a place to put them, gets
signed URLs for a multipart upload, PUTs the parts straight at Cloudflare, and
then tells us it is done — at which point we make the `File` row with `r2_key`
already set, so `OneSpaceFile.after_insert` knows there is nothing left to move.

Three things this has to get right, and each of them is why a handshake rather
than a single "give me a URL" call:

**The quota is checked before anything is signed.** A full workspace must be a
refusal in the browser, not two gigabytes uploaded and then thrown away. The
`before_insert` hook still runs at the end and is still authoritative — it sees
the object's real size, from R2, rather than the size the browser claimed.

**A caller cannot finish somebody else's upload.** `begin` returns an HMAC over
the key, the upload id and the session user; `finish` and `abort` will not touch
a multipart upload without it. That is stateless on purpose: an in-flight upload
is not worth a doctype and a row to clean up.

**A failed insert takes the object with it.** If the quota hook throws after the
parts have landed, the object is aborted and deleted before the error goes back
— otherwise a refused upload would still be billed for.

Permissions are checked twice, at `begin` and again at `finish`, against the
same folder or attached document the row will name. `finish` does not trust the
handshake for anything except who started it.
"""

import hashlib
import hmac
import json
import math
import uuid

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.password import get_encryption_key

from oneapp.onespace import site
from oneapp.onestorage import quota, r2

#: Under this an ordinary POST is the better trade: three round trips and a
#: multipart upload to save a second is not a saving. Kept in step with
#: `frontend/src/lib/directUpload.js`, which asks first and does not call at all
#: below the same number.
THRESHOLD = 8 * 1024 * 1024

#: R2, like S3, requires every part but the last to be exactly this size, and
#: allows 10,000 of them. 16 MiB covers 156 GB before the part count matters,
#: and is large enough that the per-part overhead disappears.
MIN_PART = 16 * 1024 * 1024
MAX_PARTS = 9_000

#: Long enough that a part does not expire mid-flight on a slow connection,
#: short enough that a leaked URL is not a standing grant. URLs are minted a
#: batch at a time as the upload walks forward, so this bounds one batch and not
#: the whole upload.
SIGN_TTL = 3600
BATCH = 50

#: The route a private file is read through, and — because it starts with
#: `/api/method/` — the prefix that tells `File` there is nothing on disk to go
#: looking for.
DOWNLOAD = "/api/method/oneapp.onestorage.r2.download"


# --------------------------------------------------------------------------- #
# The handshake
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def begin(
	file_name: str,
	file_size: int,
	folder: str = "",
	attached_to_doctype: str = "",
	attached_to_name: str = "",
	attached_to_field: str = "",
	is_private: int = 1,
) -> dict:
	"""Reserve a place in R2 for a file the browser is about to send.

	Answers `{"direct": False}` rather than throwing whenever the direct path
	does not apply — no R2 keys, no boto3, the control site, a small file. The
	browser reads that as "post it the ordinary way", so a development site with
	no bucket keeps working and nothing has to know why.
	"""
	size = int(file_size or 0)
	name = _safe_name(file_name)

	_may_write(folder, attached_to_doctype, attached_to_name)

	# Before anything is signed. The point of the whole handshake.
	quota.check_room(size)

	if site.is_control() or not r2.is_configured() or size < THRESHOLD:
		return {"direct": False}

	scope = "private" if int(is_private or 0) else "public"
	key = f"tenants/{r2.config()['tenant']}/{scope}/uploads/{uuid.uuid4().hex}/{name}"

	started = r2.client().create_multipart_upload(
		Bucket=r2.config()["bucket"],
		Key=key,
		ContentType=r2.guess_content_type(name),
	)
	upload_id = started["UploadId"]

	part_size = _part_size(size)
	parts = max(math.ceil(size / part_size), 1)

	return {
		"direct": True,
		"key": key,
		"upload_id": upload_id,
		"token": _token(key, upload_id),
		"part_size": part_size,
		"parts": parts,
		"urls": _sign(key, upload_id, 1, min(parts, BATCH)),
	}


@frappe.whitelist(methods=["POST"])
def sign(key: str, upload_id: str, token: str, first: int, count: int) -> dict:
	"""URLs for the next run of parts.

	Minted as the upload walks rather than all at once, so a URL is never older
	than the batch that needed it — a 40 GB upload signed up front would reach
	its last part with an hour-expired signature.
	"""
	_verify(key, upload_id, token)
	first = max(int(first or 1), 1)
	count = min(max(int(count or 1), 1), BATCH)
	return {"urls": _sign(key, upload_id, first, count)}


@frappe.whitelist(methods=["POST"])
def finish(
	key: str,
	upload_id: str,
	token: str,
	parts,
	file_name: str,
	folder: str = "",
	attached_to_doctype: str = "",
	attached_to_name: str = "",
	attached_to_field: str = "",
) -> dict:
	"""Assemble the parts and make the `File` row that points at them.

	Takes no `is_private`: whether the file is private was decided at `begin`
	and is written into the key, which the token vouches for. Asking again here
	would be asking a question we already have a trustworthy answer to.
	"""
	_verify(key, upload_id, token)
	_may_write(folder, attached_to_doctype, attached_to_name)

	# Shaped before the try, so a malformed payload is a refusal the browser can
	# send again rather than an abort that destroys an upload which had actually
	# arrived.
	shaped = _parts(parts)

	client = r2.client()
	bucket = r2.config()["bucket"]

	try:
		client.complete_multipart_upload(
			Bucket=bucket,
			Key=key,
			UploadId=upload_id,
			MultipartUpload={"Parts": shaped},
		)
	except Exception:
		# A completion R2 refused leaves the parts behind, billed, with nothing
		# that will ever assemble them.
		abort(key, upload_id, token)
		raise

	# What R2 says it holds, not what the browser said it would send. The quota
	# is enforced against this.
	size = int(client.head_object(Bucket=bucket, Key=key)["ContentLength"])

	try:
		doc = _row(
			key=key,
			file_name=_safe_name(file_name),
			size=size,
			folder=folder,
			attached_to_doctype=attached_to_doctype,
			attached_to_name=attached_to_name,
			attached_to_field=attached_to_field,
			# Off the key, which the token vouches for. A row disagreeing with
			# its own object would be a public file behind a permission check,
			# or the reverse.
			is_private=_is_private(key),
		)
	except Exception:
		# The bytes are in the bucket and no row will ever point at them. An
		# upload the workspace was refused must not be an object it is billed
		# for.
		r2.delete(key)
		raise

	return {
		"ok": True,
		"name": doc.name,
		"file_name": doc.file_name,
		"file_url": doc.file_url,
		"file_size": doc.file_size,
	}


@frappe.whitelist(methods=["POST"])
def abort(key: str, upload_id: str, token: str) -> dict:
	"""Drop a multipart upload that will not be finished.

	Worth calling: R2 bills for the parts of an abandoned multipart upload until
	a lifecycle rule sweeps them, and the browser knows it has given up long
	before any sweep would.
	"""
	_verify(key, upload_id, token)
	try:
		r2.client().abort_multipart_upload(
			Bucket=r2.config()["bucket"], Key=key, UploadId=upload_id
		)
	except Exception:
		frappe.log_error(title="R2 abort failed", message=frappe.get_traceback())
		return {"ok": False}
	return {"ok": True}


# --------------------------------------------------------------------------- #
# Bytes already in hand
# --------------------------------------------------------------------------- #
#
# Not part of the handshake, and here for the same reason the handshake is:
# `File.insert(content=…)` writes the bytes to local disk, and
# `OneSpaceFile.after_insert` then reads them back, uploads them and deletes
# the copy. That round trip is invisible when the file is a photograph and is
# the whole cost when it is a drawing set.
#
# A caller that cannot stream — WebDAV's PUT, where Frappe has already read the
# whole body into memory before any of our code runs — still need not pay for
# the disk. These put the bytes in the bucket and make the row point at them,
# which is exactly what `finish` does with bytes it never saw.

def _fresh_key(file_name: str, is_private) -> str:
	"""Where a new object goes. The shape `begin` signs, and `_is_private`
	reads the scope back out of."""
	scope = "private" if int(is_private or 0) else "public"
	return f"tenants/{r2.config()['tenant']}/{scope}/uploads/{uuid.uuid4().hex}/{file_name}"


def land(content: bytes, file_name: str, folder: str = "", is_private: int = 1,
         attached_to_doctype: str = "", attached_to_name: str = ""):
	"""A new `File` whose bytes go straight to R2.

	The quota is asked before the object is written and enforced again by
	`File.before_insert` afterwards, which is the same order `begin`/`finish`
	use and for the same reason: an upload the workspace has no room for must
	not be an object it is billed for.

	`attached_to_*` is what makes a file land *on a record*: the same triple
	the browser's attach path writes, which is how a PUT into a mounted
	`doctype:Quotation/QTN-0001/` becomes an attachment rather than a loose
	file in a folder — see `scopes.py`.
	"""
	name = _safe_name(file_name)
	content = content if isinstance(content, bytes) else (content or "").encode("utf-8")

	if site.is_control() or not r2.is_configured():
		# No bucket to put it in. The ordinary path, where the bytes land on
		# disk and `after_insert` finds nothing to move.
		return frappe.get_doc({
			"doctype": "File",
			"file_name": name,
			"folder": folder or None,
			"attached_to_doctype": attached_to_doctype or None,
			"attached_to_name": attached_to_name or None,
			"is_private": 1 if is_private else 0,
			"content": content,
		}).insert()

	quota.check_room(len(content))

	key = _fresh_key(name, is_private)

	r2.client().put_object(
		Bucket=r2.config()["bucket"],
		Key=key,
		Body=content,
		ContentType=r2.guess_content_type(name),
	)

	try:
		return _row(
			key=key,
			file_name=name,
			size=len(content),
			folder=folder,
			attached_to_doctype=attached_to_doctype,
			attached_to_name=attached_to_name,
			attached_to_field="",
			is_private=1 if is_private else 0,
		)
	except Exception:
		r2.delete(key)
		raise


def replace(doc, content: bytes):
	"""New bytes for a file that already exists, over the object it owns.

	The same key wherever it can be, so every link to it keeps working — a
	share URL, an `img src` in a document. The exception is a key a second row
	also points at, below. Only the difference in size is charged against the
	quota, because only the difference is what the workspace ends up holding.
	"""
	content = content if isinstance(content, bytes) else (content or "").encode("utf-8")
	key = doc.get("r2_key")

	if not key or site.is_control() or not r2.is_configured():
		doc.save_file(content=content, overwrite=True)
		doc.save()
		return doc

	quota.check_room(max(len(content) - cint(doc.file_size), 0))

	# A second `File` over one object is what attaching a Drive file to a
	# record writes, and writing over that object would change the file on
	# every record holding it. So a shared key is not overwritten: this row
	# gets a new object and the others keep the old one.
	if doc.shared_object(key):
		key = _fresh_key(_safe_name(doc.file_name), doc.is_private)

	r2.client().put_object(
		Bucket=r2.config()["bucket"],
		Key=key,
		Body=content,
		ContentType=r2.guess_content_type(doc.file_name),
	)

	from frappe.core.doctype.file.utils import get_content_hash

	# `modified` moves with it: a WebDAV client reads `Last-Modified` back to
	# decide whether its own copy is stale, and a file whose bytes changed
	# while its timestamp did not is one it will never fetch again.
	doc.db_set(
		{
			"file_size": len(content),
			"content_hash": get_content_hash(content),
			"r2_key": key,
			"file_url": _url(doc, key),
		},
		update_modified=True,
	)
	return doc


def duplicate(doc, file_name: str, folder: str = "",
              attached_to_doctype: str = "", attached_to_name: str = ""):
	"""A second file holding the same bytes.

	R2 copies it inside the bucket, so a 300 MB drawing is a metadata call
	rather than a download and an upload through a request worker. A new key
	and not a second row over the old one, because these two files are
	separately editable from the moment they exist.

	`attached_to_*` for the same reason `land` takes it: a COPY into a mounted
	record's directory is an attachment on that record.
	"""
	name = _safe_name(file_name)
	key = doc.get("r2_key")

	if not key or site.is_control() or not r2.is_configured():
		return land(doc.get_content(), file_name=name, folder=folder,
		            is_private=doc.is_private,
		            attached_to_doctype=attached_to_doctype,
		            attached_to_name=attached_to_name)

	client = r2.client()
	bucket = r2.config()["bucket"]

	# What the bucket says it holds, not what the row says — the same reason
	# `finish` asks: the quota below is enforced against this number, and a
	# row whose `file_size` drifted would charge for the wrong thing.
	size = cint(client.head_object(Bucket=bucket, Key=key)["ContentLength"])
	quota.check_room(size)

	fresh = _fresh_key(name, doc.is_private)
	client.copy_object(
		Bucket=bucket,
		Key=fresh,
		CopySource={"Bucket": bucket, "Key": key},
		ContentType=r2.guess_content_type(name),
		MetadataDirective="REPLACE",
	)

	try:
		return _row(
			key=fresh,
			file_name=name,
			size=size,
			folder=folder,
			attached_to_doctype=attached_to_doctype,
			attached_to_name=attached_to_name,
			attached_to_field="",
			is_private=1 if doc.is_private else 0,
		)
	except Exception:
		r2.delete(fresh)
		raise


# --------------------------------------------------------------------------- #
# The row
# --------------------------------------------------------------------------- #

def _row(
	key: str,
	file_name: str,
	size: int,
	folder: str,
	attached_to_doctype: str,
	attached_to_name: str,
	attached_to_field: str,
	is_private: int,
):
	"""Insert the `File` that owns this object.

	The awkward part is `file_url`, and it is awkward in both directions. A
	private file's URL names its own row, and the row has no name until Frappe
	has given it one — so the real URL can only be written after the insert.
	But it cannot simply be left empty until then either: `validate_file_on_disk`
	does not ask whether the file is remote, it asks whether the path starts
	with a URL prefix, and an empty one does not — so an empty `file_url` fails
	the insert with `File  does not exist`, with the name of the missing file
	blank because there is no name.

	So it goes in twice: a placeholder that is unambiguously remote and unique
	to this upload, then the real one. Unique because `validate_private_file_access`
	looks up other rows carrying the same URL, and a shared placeholder would
	make one abandoned upload refuse the next person's.

	`r2_key` is in the dict rather than written after, and has to be:
	`OneSpaceFile.after_insert` reads it to decide whether to move the bytes,
	and the bytes are already there.
	"""
	doc = frappe.get_doc({
		"doctype": "File",
		"file_name": file_name,
		"folder": folder or None,
		"is_private": 1 if is_private else 0,
		"file_size": size,
		"file_url": f"{DOWNLOAD}?pending={key}",
		"r2_key": key,
		"attached_to_doctype": attached_to_doctype or None,
		"attached_to_name": attached_to_name or None,
		"attached_to_field": attached_to_field or None,
	})
	doc.insert()

	doc.db_set("file_url", _url(doc, key), update_modified=False)
	return doc


def _is_private(key: str) -> bool:
	"""What `begin` decided, read back off the key it signed."""
	return "/private/uploads/" in key


def _url(doc, key: str) -> str:
	"""Where this file is read from — the same two answers `r2.upload` gives."""
	if doc.is_private:
		return f"{DOWNLOAD}?file={doc.name}"

	base = r2.config()["public_base"]
	if base:
		return f"{base}/{key}"

	return f"{DOWNLOAD}?file={doc.name}"


# --------------------------------------------------------------------------- #
# Permission, signature, shape
# --------------------------------------------------------------------------- #

def _may_write(folder: str, doctype: str, docname: str):
	"""Whoever may put a file here.

	Three cases and they are genuinely different: an attachment is governed by
	the document it hangs off, a Drive file by the folder it lands in, and a
	loose file by nothing but the right to create one.
	"""
	if doctype and docname:
		frappe.get_doc(doctype, docname).check_permission("write")
		return

	if folder:
		frappe.get_doc("File", folder).check_permission("write")
		return

	if not frappe.has_permission("File", "create"):
		frappe.throw(_("Not permitted."), frappe.PermissionError)


def _token(key: str, upload_id: str) -> str:
	"""An HMAC binding this upload to the person who started it.

	Stateless because the alternative is a row per in-flight upload and a sweep
	for the ones nobody finished. The session user is inside the digest, so a
	stolen key and upload id are not enough — the thief's own token would not
	verify against them.
	"""
	message = f"{key}|{upload_id}|{frappe.session.user}".encode()
	secret = get_encryption_key().encode()
	return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _verify(key: str, upload_id: str, token: str):
	if not hmac.compare_digest(_token(key, upload_id), token or ""):
		frappe.throw(_("This upload is not yours to finish."), frappe.PermissionError)


def _sign(key: str, upload_id: str, first: int, count: int) -> list[dict]:
	client = r2.client()
	bucket = r2.config()["bucket"]
	return [
		{
			"part": number,
			"url": client.generate_presigned_url(
				"upload_part",
				Params={
					"Bucket": bucket,
					"Key": key,
					"UploadId": upload_id,
					"PartNumber": number,
				},
				ExpiresIn=SIGN_TTL,
			),
		}
		for number in range(first, first + count)
	]


def _part_size(size: int) -> int:
	"""Big enough that the part count stays under R2's ceiling.

	Rounded up to whole MiB, because every part but the last must be exactly
	this and an awkward number here is an awkward number in the browser's
	`slice` arithmetic for the whole upload.
	"""
	needed = math.ceil(max(size, 1) / MAX_PARTS)
	mib = 1024 * 1024
	return max(MIN_PART, math.ceil(needed / mib) * mib)


def _parts(parts) -> list[dict]:
	"""The `{PartNumber, ETag}` list R2 completes an upload with.

	Sorted here rather than trusted from the browser: parts are uploaded in
	parallel and arrive back in whatever order they finished, and S3 rejects a
	completion whose part numbers are not ascending.
	"""
	if isinstance(parts, str):
		parts = json.loads(parts)

	shaped = [
		{"PartNumber": int(one["part"]), "ETag": str(one["etag"])}
		for one in parts or []
	]
	if not shaped:
		frappe.throw(_("That upload sent no parts."))

	return sorted(shaped, key=lambda one: one["PartNumber"])


def _safe_name(file_name: str) -> str:
	"""A file name with no path in it.

	The name goes into an object key. A `../` in it would be a file written
	outside its tenant's prefix, which is the one mistake in here that would be
	somebody else's problem rather than ours.
	"""
	name = (file_name or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
	if not name or name in (".", ".."):
		frappe.throw(_("That file has no name."))
	return name
