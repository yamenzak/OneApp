"""The other direction: a Drive folder that *is* a WebDAV share.

`remote.py` mounts somebody else's server here. This serves ours to them — so
a folder in the Drive appears in Finder, in Windows Explorer, in Nextcloud's
external-storage list and to anything else that speaks WebDAV, and the files
in it are the same `File` rows every other surface draws.

## Why WebDAV and not SFTP

WebDAV is HTTP. It rides the port the site already answers on, inside the
process that is already running, behind the reverse proxy that already has the
certificate. SFTP is a subsystem of SSH: it needs a daemon, a listening port,
a host key and something to keep the daemon alive — a second runtime, which
this product has refused twice before (`docs/COLLABORATION.md` §1) and which a
tenant on Frappe Cloud has nowhere to put. The two look like a pair from the
client side and are nothing like a pair from ours.

## How it gets a request at all

Frappe's dispatcher answers `/api/...` for any method and routes GET, HEAD and
POST to the website; **everything else raises NotFound** (`frappe/app.py`), so
PROPFIND on a path of ours is a 404 before any code of ours runs.

The way in is `before_request`, which runs after `frappe.connect()` and before
both `validate_auth()` and that dispatch. The hook builds a whole response and
raises it as an `HTTPException` whose `get_response` hands it back — which is
the one shape `application()` returns verbatim rather than re-rendering.

Two consequences, and both are load-bearing:

* **This route authenticates itself.** `validate_auth` has not run, so there is
  no session and no CSRF. That is what we want — a WebDAV client sends HTTP
  Basic and nothing else — but it means every check on this path is ours.
* **The framework rolls back after an exception**, including ours. So anything
  that writes commits before it returns. Every handler below that changes
  something does, and a test reads the list back.

## What a key is

Not the account password. A `Drive Access` is a generated username and a
generated secret, scoped to one folder, optionally read-only, optionally
expiring — and it acts *as* the person who made it, so it can never reach a
file they could not. Revoking one is a row, not a password reset.

The secret is stored as a SHA-256 digest rather than reversibly. It is 32
bytes from `secrets.token_urlsafe`, so there is nothing to brute-force and
nothing to be careful with: the plaintext exists once, in the dialog that
made it.

## What it does not do

Ranged GET. And locks are answered but not enforced: Finder and Office refuse
to write to a share that 501s LOCK, and a real lock table is a promise about
concurrent writers that several processes behind a load balancer cannot keep.

## Why a PUT is capped, and what the cap is not

A PUT's bytes go straight from the request to R2 and the `File` row is made
already pointing at the object — `direct.land`, the same landing the browser's
multipart upload uses. There is no local disk in the path.

What there is, is a ceiling, and it is not ours: `init_request` sets
`request.max_content_length` from the site's `max_file_size` and then calls
`make_form_dict`, which reads the whole body. Both happen before the first
`before_request` hook, so by the time any code here runs the body is either
already in memory or already refused — there is no seam in the app for a
streaming PUT, and no WSGI middleware hook to put one in. Raising the number
means raising `max_file_size` in the site config, which raises it for every
upload on the site; `_too_big` says so, and `explain_refusal` rewrites the
framework's own HTML 413 into that sentence so a client actually shows it.

Past that ceiling the answer is the Drive in a browser, which signs a
multipart upload and sends the parts at Cloudflare without passing through
Python at all (`direct.py`).
"""

import hashlib
import secrets
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlsplit
from xml.sax.saxutils import escape

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from . import limits
from .kinds import ACTIVE, STATUS_FIELD
from .query import ROOT, _visible
from .quota import format_bytes

#: Where the share answers. One path for every key: the credential decides
#: what is behind it, which is how every other WebDAV server works and is why
#: a person with two keys does not need two URLs.
PREFIX = "/dav"

#: What a key's secret looks like before it is hashed. 32 bytes is past the
#: point where a digest needs a salt or a work factor.
SECRET_BYTES = 32

#: Methods answered. `PROPPATCH` is in the list because Finder sets a
#: modification time on every write and treats a 405 as a failed copy; it is
#: accepted and ignored, which is what the RFC allows for a property a server
#: does not keep.
METHODS = (
	"OPTIONS", "PROPFIND", "PROPPATCH", "GET", "HEAD", "PUT", "MKCOL",
	"DELETE", "MOVE", "COPY", "LOCK", "UNLOCK",
)

#: Which of those change something. Read-only keys are refused all of them.
WRITES = ("PUT", "MKCOL", "DELETE", "MOVE", "COPY", "PROPPATCH")


def _ceiling() -> int:
	"""The largest body this share can be handed.

	`limits.posted_ceiling()`, which is the same number the browser's attach
	controls print under themselves — said in one place so a site that raises
	`max_file_size` raises both.
	"""
	return limits.posted_ceiling()


def _too_big(size: int = 0) -> str:
	"""Why a PUT was refused, said where somebody can act on it.

	Two whole sentences rather than one assembled from pieces, because a
	chunked body has no length to name and a translator cannot be handed half
	a sentence — `docs/LANGUAGE.md`.
	"""
	if size:
		return _(
			"This file is {0} and the largest a WebDAV upload can be here is {1}, "
			"because the framework reads the whole request body before this share "
			"sees it. Upload it through the Drive in a browser instead, which sends "
			"large files straight to storage in parts, or raise max_file_size in the "
			"site configuration."
		).format(format_bytes(size), format_bytes(_ceiling()))

	return _(
		"The largest a WebDAV upload can be here is {0}, because the framework "
		"reads the whole request body before this share sees it. Upload it through "
		"the Drive in a browser instead, which sends large files straight to storage "
		"in parts, or raise max_file_size in the site configuration."
	).format(format_bytes(_ceiling()))


def explain_refusal(response=None, request=None):
	"""after_request: give the framework's own 413 a body a client can show.

	The refusal that matters is not `_put`'s — it is werkzeug's, raised inside
	`make_form_dict` while `_ceiling` bytes of the body are being read, long
	before this module is asked anything. Frappe renders that as an HTML error
	page, which a file manager displays as nothing at all.

	This is the one place downstream of it: `run_after_request_hooks` runs in
	`application`'s `finally`, so it sees the response for a request that never
	reached a handler. Everything else passes through untouched.
	"""
	try:
		if response is None or request is None:
			return
		if response.status_code != 413 or not request.path.startswith(PREFIX):
			return

		response.set_data(_too_big(cint(request.content_length)))
		response.content_type = "text/plain; charset=utf-8"
	except Exception:
		# An after_request hook that throws loses the response Frappe was
		# about to send. A 413 nobody can read is better than a 500.
		pass


def _reply(body=b"", status: int = 200, **kw):
	"""A werkzeug `Response`, with werkzeug imported where it is used.

	Lazily, like `paramiko` in `remote.py` and for a plainer reason: the unit
	suite runs without a bench (`tests/conftest.py` stubs frappe entirely) and
	has no werkzeug, so a module-scope import here would break every test that
	imports anything under `onestorage` — which is most of them. Nothing calls
	into this module outside a request, where werkzeug is always present.
	"""
	from werkzeug.wrappers import Response

	return Response(body, status=status, **kw)


def _answered(response):
	"""The response, wrapped in the one exception `application()` hands back.

	Built here rather than declared at module scope because its base class is
	werkzeug's — see `_reply`. `application` re-renders an ordinary exception
	into Frappe's JSON error shape, which a WebDAV client cannot read; an
	`HTTPException` it returns as-is.
	"""
	from werkzeug.exceptions import HTTPException

	class _Answered(HTTPException):
		def __init__(self, ready):
			super().__init__()
			self.response = ready

		def get_response(self, environ=None, scope=None):
			return self.response

	return _Answered(response)


def intercept():
	"""`before_request`. Answers `/dav` and gets out of the way otherwise."""
	request = getattr(frappe.local, "request", None)
	if not request:
		return
	path = request.path or ""
	if path != PREFIX and not path.startswith(PREFIX + "/"):
		return

	raise _answered(serve(request))


# --------------------------------------------------------------------------- #
# The door
# --------------------------------------------------------------------------- #

def serve(request):
	"""One request, from the credential to the response.

	Every failure is a status and, all but once, a bare body: a WebDAV client
	shows the status and discards the rest, so a sentence here is a sentence
	nobody reads — where a person finds out why is the key's own screen. The
	exception is the size refusal, which the command-line clients do print and
	which a person can do something about.
	"""
	if request.method not in METHODS:
		return _reply(status=405, headers={"Allow": ", ".join(METHODS)})

	key = _key_for(request)
	if not key:
		return _unauthorized()

	if request.method == "OPTIONS":
		return _options()

	if request.method in WRITES and key.read_only:
		return _reply(status=403)

	try:
		handler = {
			"PROPFIND": _propfind, "GET": _get, "HEAD": _get, "PUT": _put,
			"MKCOL": _mkcol, "DELETE": _delete, "MOVE": _move, "COPY": _copy,
			"LOCK": _lock, "UNLOCK": _unlock, "PROPPATCH": _proppatch,
		}[request.method]
		return handler(request, key)
	except _Status as answered:
		if answered.body:
			return _reply(
				answered.body, status=answered.code,
				headers=answered.headers or {},
				content_type="text/plain; charset=utf-8",
			)
		return _reply(status=answered.code, headers=answered.headers or {})
	except frappe.PermissionError:
		return _reply(status=403)
	except Exception:
		frappe.log_error(title="WebDAV request failed", message=frappe.get_traceback())
		if frappe.local.conf.get("developer_mode"):
			# The status is all a client shows, so on a dev site the traceback
			# goes in the body too — otherwise the only way to see why a verb
			# failed is to go and find the Error Log.
			return _reply(frappe.get_traceback(), status=500, content_type="text/plain")
		return _reply(status=500)


class _Status(Exception):
	"""A status a handler wants to answer with, and nothing else."""

	def __init__(self, code: int, headers: dict | None = None, body: str = ""):
		super().__init__(code)
		self.code = code
		self.headers = headers
		self.body = body


#: The challenge, which has to be set twice.
#:
#: Frappe's `process_response` replaces `WWW-Authenticate` with an OAuth
#: Bearer challenge on *any* 401 once OAuth resource metadata is enabled on
#: the site — and a client told to use Bearer never shows a password box, so
#: the share simply cannot be mounted. It applies `frappe.local.response_headers`
#: immediately afterwards, which is the supported way to have the last word.
CHALLENGE = 'Basic realm="OneSpace files", charset="UTF-8"'


def _unauthorized():
	# The realm is what a browser and Finder put above the password box.
	frappe.local.response_headers["WWW-Authenticate"] = CHALLENGE
	return _reply(status=401, headers={"WWW-Authenticate": CHALLENGE})


def _options():
	# `DAV: 1, 2` and not `1`: class 2 is what says locks exist, and Finder
	# mounts a class-1 share read-only however the files are permissioned.
	return _reply(status=200, headers={
		"DAV": "1, 2",
		"MS-Author-Via": "DAV",
		"Allow": ", ".join(METHODS),
		"Content-Length": "0",
	})


# --------------------------------------------------------------------------- #
# Who is asking
# --------------------------------------------------------------------------- #

def _key_for(request):
	"""The `Drive Access` behind this request's Basic auth, or None.

	Sets `frappe.session.user` to the key's owner, which is what makes every
	read below behave as that person — a key cannot reach a file its owner
	could not, and nothing here re-implements a permission.
	"""
	auth = request.authorization
	if not auth or not auth.username or not auth.password:
		return None

	row = frappe.db.get_value(
		"Drive Access",
		{"access_user": auth.username, "enabled": 1},
		["name", "owner", "label", "folder", "read_only", "expires_on", "secret_hash"],
		as_dict=True,
	)
	if not row:
		return None

	# `compare_digest`, because a plain `==` on a secret leaks its prefix in
	# the time it takes to fail.
	if not secrets.compare_digest(row.secret_hash or "", digest(auth.password)):
		return None
	if row.expires_on and frappe.utils.get_datetime(row.expires_on) < now_datetime():
		return None

	frappe.set_user(row.owner)
	# Stamped on a read as well as a write, because "is anything still using
	# this key" is the question that decides whether it can be revoked.
	frappe.db.set_value("Drive Access", row.name, "last_used", now_datetime(),
	                    update_modified=False)
	frappe.db.commit()
	return row


def digest(secret: str) -> str:
	return hashlib.sha256((secret or "").encode()).hexdigest()


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

def _parts(request) -> list[str]:
	"""The path under `/dav`, as decoded segments with no way upwards."""
	rest = unquote(request.path)[len(PREFIX):]
	found = [one for one in rest.split("/") if one not in ("", ".")]
	if any(one == ".." for one in found):
		raise _Status(403)
	return found


def _root(key) -> str:
	"""The `File` the key is scoped to. `Home` is the whole Drive."""
	return key.folder or ROOT


def _walk(key, parts: list[str], missing_ok: bool = False):
	"""Resolve segments to a `File` row, one `file_name` lookup at a time.

	By name within a parent rather than by Frappe's `Home/Drawings` id: the id
	is built from the name and the two come apart the moment anything is
	renamed, and a client's path is names all the way down.

	Returns `(row, None, "")` for something that exists, and — when
	`missing_ok` and only the last segment is missing — `(None, parent, leaf)`,
	which is what PUT and MKCOL need to create one.
	"""
	at = frappe.db.get_value("File", _root(key), ["name", "is_folder", "file_name"],
	                         as_dict=True)
	if not at:
		raise _Status(404)

	for segment in parts:
		if not at.is_folder:
			raise _Status(404)
		row = frappe.db.get_value(
			"File",
			{"folder": at.name, "file_name": segment,
			 STATUS_FIELD: ("in", (ACTIVE, "", None))},
			["name", "is_folder", "file_name"], as_dict=True,
		)
		if not row:
			if missing_ok and segment == parts[-1]:
				return None, at, segment
			raise _Status(404)
		at = row

	return at, None, ""


def _href(parts: list[str], is_folder: bool) -> str:
	"""What goes in a `<D:href>`: the same path, quoted, folders with a slash."""
	path = PREFIX + "".join("/" + quote(one) for one in parts)
	return path + "/" if is_folder else path


def _destination(request) -> list[str]:
	"""The `Destination` header of a MOVE or COPY, as segments under the key."""
	target = request.headers.get("Destination") or ""
	if not target:
		raise _Status(400)
	path = unquote(urlsplit(target).path)
	if not path.startswith(PREFIX):
		# A destination outside the share is one this server cannot reach.
		raise _Status(502)
	found = [one for one in path[len(PREFIX):].split("/") if one not in ("", ".")]
	if any(one == ".." for one in found):
		raise _Status(403)
	return found


# --------------------------------------------------------------------------- #
# PROPFIND
# --------------------------------------------------------------------------- #

def _prop_xml(href: str, row: dict) -> str:
	"""One `<D:response>`.

	Four properties, and the same four for `allprop`: a server may answer that
	with what it likes, and SharePoint answering it with three hundred lines
	per entry is the reason not to be generous.
	"""
	is_folder = bool(row.get("is_folder"))
	stamp = _http_date(row.get("modified") or row.get("creation"))
	body = [
		"<D:response>",
		f"<D:href>{escape(href)}</D:href>",
		"<D:propstat><D:prop>",
		f"<D:displayname>{escape(row.get('file_name') or '')}</D:displayname>",
		"<D:resourcetype><D:collection/></D:resourcetype>" if is_folder
		else "<D:resourcetype/>",
		f"<D:getlastmodified>{stamp}</D:getlastmodified>",
	]
	if not is_folder:
		body.append(
			f"<D:getcontentlength>{cint(row.get('file_size'))}</D:getcontentlength>"
		)
	body += [
		"</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>",
		"</D:response>",
	]
	return "".join(body)


def _http_date(when) -> str:
	"""An RFC 1123 date in GMT, which is the only form a DAV client reads.

	Frappe stores datetimes naive and in the *site's* timezone, and
	`format_datetime(usegmt=True)` refuses anything that is not aware UTC —
	so this attaches the site's zone and converts. Skipping the conversion
	and just stamping `+0000` would be the easy version and would be wrong by
	the site's offset, which a client reads as every file having changed.
	"""
	from email.utils import format_datetime
	from zoneinfo import ZoneInfo

	if not when:
		when = datetime(1970, 1, 1)
	if isinstance(when, str):
		when = frappe.utils.get_datetime(when)
	if when.tzinfo is None:
		when = when.replace(tzinfo=ZoneInfo(frappe.utils.get_system_timezone()))
	return format_datetime(when.astimezone(timezone.utc), usegmt=True)


def _propfind(request, key):
	depth = (request.headers.get("Depth") or "1").strip().lower()
	if depth not in ("0", "1"):
		# RFC 4918 lets a server refuse infinite depth, and it must: the
		# alternative is one request that walks a whole Drive.
		return _multistatus_error(403, "propfind-finite-depth")

	parts = _parts(request)
	row, _parent, _leaf = _walk(key, parts)
	full = frappe.db.get_value(
		"File", row.name,
		["name", "file_name", "is_folder", "file_size", "modified", "creation"],
		as_dict=True,
	)
	# The share's own root is named for the key rather than for the folder id,
	# so a mount does not announce itself as `Home`.
	if not parts:
		full.file_name = key.label or full.file_name

	out = [_prop_xml(_href(parts, bool(full.is_folder)), full)]
	if depth == "1" and full.is_folder:
		# `get_list` and not `get_all`: the key acts as its owner, and this is
		# the query that applies that.
		for child in frappe.get_list(
			"File",
			filters={"folder": row.name, **_visible()},
			fields=["name", "file_name", "is_folder", "file_size", "modified", "creation"],
			order_by="is_folder desc, file_name asc",
			limit_page_length=0,
		):
			out.append(_prop_xml(
				_href(parts + [child.file_name], bool(child.is_folder)), child
			))

	return _multistatus("".join(out))


def _multistatus(body: str):
	return _reply(
		'<?xml version="1.0" encoding="utf-8"?>'
		f'<D:multistatus xmlns:D="DAV:">{body}</D:multistatus>',
		status=207, content_type='application/xml; charset="utf-8"',
	)


def _multistatus_error(status: int, tag: str):
	return _reply(
		'<?xml version="1.0" encoding="utf-8"?>'
		f'<D:error xmlns:D="DAV:"><D:{tag}/></D:error>',
		status=status, content_type='application/xml; charset="utf-8"',
	)


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

def _get(request, key):
	row, _parent, _leaf = _walk(key, _parts(request))
	doc = frappe.get_doc("File", row.name)
	doc.check_permission("read")
	if doc.is_folder:
		# A GET on a collection has no defined meaning and no client does it;
		# 405 is what every other server answers.
		raise _Status(405, {"Allow": ", ".join(METHODS)})

	from .r2 import guess_content_type

	headers = {
		"Content-Type": guess_content_type(doc.file_name),
		"Last-Modified": _http_date(doc.modified),
	}
	if request.method == "HEAD":
		headers["Content-Length"] = str(cint(doc.file_size))
		return _reply(status=200, headers=headers)

	return _reply(doc.get_content(), status=200, headers=headers)


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

def _put(request, key):
	parts = _parts(request)
	if not parts:
		raise _Status(405)

	content = request.get_data()
	if len(content) > _ceiling():
		# Rarely reached: werkzeug refuses on Content-Length while
		# `make_form_dict` reads, and `explain_refusal` answers that one. This
		# is the chunked body, which has no length to refuse on.
		raise _Status(413, body=_too_big(len(content)))

	from . import direct

	row, parent, leaf = _walk(key, parts, missing_ok=True)
	if row:
		doc = frappe.get_doc("File", row.name)
		doc.check_permission("write")
		if doc.is_folder:
			raise _Status(405)
		# Over the object the row already owns, so every link to it survives
		# an overwrite — and only the difference in size is charged.
		direct.replace(doc, content)
		frappe.db.commit()
		return _reply(status=204)

	# Straight into the bucket, and the row made already pointing at it —
	# `File.insert(content=…)` would write the bytes to local disk for
	# `after_insert` to read back, upload and delete. `land` still inserts a
	# `File`, so `before_insert` still enforces the quota and stamps the kind
	# (see `hooks.py`); a PUT that went round that would be the one upload
	# path that does not count.
	direct.land(content, file_name=leaf, folder=parent.name, is_private=1)
	frappe.db.commit()
	return _reply(status=201, headers={"Location": _href(parts, False)})


def _mkcol(request, key):
	if request.get_data():
		# A body on MKCOL means an extended MKCOL, which this does not do.
		raise _Status(415)

	parts = _parts(request)
	if not parts:
		raise _Status(405)

	row, parent, leaf = _walk(key, parts, missing_ok=True)
	if row:
		raise _Status(405)

	from .writing import make_folder

	make_folder(file_name=leaf, folder=parent.name)
	frappe.db.commit()
	return _reply(status=201)


def _delete(request, key):
	parts = _parts(request)
	if not parts:
		# Deleting the share itself is not a thing a client may do.
		raise _Status(403)

	row, _parent, _leaf = _walk(key, parts)

	from .writing import trash

	# The bin, not a delete — the same thirty days every other surface gives.
	# A client showing the file gone and the Drive keeping it is the right way
	# round for a protocol where one stray keypress removes a folder.
	trash([row.name])
	frappe.db.commit()
	return _reply(status=204)


def _move(request, key):
	parts = _parts(request)
	target = _destination(request)
	if not parts or not target:
		raise _Status(403)

	row, _parent, _leaf = _walk(key, parts)
	there, parent, leaf = _walk(key, target, missing_ok=True)

	if there and (request.headers.get("Overwrite") or "T").upper() == "F":
		raise _Status(412)

	from .writing import move, rename

	if parent and parent.name != frappe.db.get_value("File", row.name, "folder"):
		move([row.name], parent.name)
	if leaf and leaf != frappe.db.get_value("File", row.name, "file_name"):
		rename(row.name, leaf)
	frappe.db.commit()
	return _reply(status=204 if there else 201)


def _copy(request, key):
	parts = _parts(request)
	target = _destination(request)
	if not parts or not target:
		raise _Status(403)

	row, _parent, _leaf = _walk(key, parts)
	source = frappe.get_doc("File", row.name)
	source.check_permission("read")
	if source.is_folder:
		# A deep copy is a loop over a subtree and a quota question per file.
		# Refused rather than half-done.
		raise _Status(403)

	there, parent, leaf = _walk(key, target, missing_ok=True)
	if there:
		raise _Status(412)

	from . import direct

	# Copied inside the bucket. Finder's way of moving a file between two
	# shares is COPY then DELETE, and pulling every byte through this process
	# to put it back a second later is the whole cost of that gesture. The
	# copy is as private as its source, which is every file a share reaches.
	direct.duplicate(source, file_name=leaf, folder=parent.name)
	frappe.db.commit()
	return _reply(status=201)


def _proppatch(request, key):
	"""Accepted and ignored. See `METHODS`.

	Finder sets a modification time on every copy and reads a 405 as the copy
	having failed, so the file appears not to have arrived when it has.
	"""
	parts = _parts(request)
	_walk(key, parts)
	return _multistatus(
		f"<D:response><D:href>{escape(_href(parts, False))}</D:href>"
		"<D:propstat><D:prop/>"
		"<D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response>"
	)


# --------------------------------------------------------------------------- #
# Locks, answered and not kept
# --------------------------------------------------------------------------- #

def _lock(request, key):
	"""A token, and no table behind it.

	A lock is a promise that no other writer will touch the file, and this
	runs in several processes behind a load balancer with no shared lock
	manager — a table would make the promise and not keep it. Finder and
	Office refuse to write to a share that 501s LOCK, so the honest options
	are "answer and do not enforce" or "no writing from a Mac", and the first
	is what every small DAV server does.
	"""
	token = f"opaquelocktoken:{secrets.token_hex(16)}"
	parts = _parts(request)
	body = (
		'<?xml version="1.0" encoding="utf-8"?>'
		'<D:prop xmlns:D="DAV:"><D:lockdiscovery><D:activelock>'
		"<D:locktype><D:write/></D:locktype>"
		"<D:lockscope><D:exclusive/></D:lockscope>"
		"<D:depth>infinity</D:depth>"
		"<D:timeout>Second-3600</D:timeout>"
		f"<D:locktoken><D:href>{token}</D:href></D:locktoken>"
		f"<D:lockroot><D:href>{escape(_href(parts, False))}</D:href></D:lockroot>"
		"</D:activelock></D:lockdiscovery></D:prop>"
	)
	return _reply(body, status=200, content_type='application/xml; charset="utf-8"',
	              headers={"Lock-Token": f"<{token}>"})


def _unlock(request, key):
	return _reply(status=204)


# --------------------------------------------------------------------------- #
# Keys, from the Drive's own screen
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def shares() -> list[dict]:
	"""Every key this person made. Never a secret — there is none to send."""
	return frappe.get_list(
		"Drive Access",
		filters={"owner": frappe.session.user},
		fields=["name", "label", "access_user", "folder", "read_only", "enabled",
		        "expires_on", "last_used", "creation"],
		order_by="creation desc",
		limit_page_length=0,
	)


@frappe.whitelist(methods=["POST"])
def share_folder(label: str = "", folder: str = "", read_only: str | int = 1,
                 days: int = 0) -> dict:
	"""Make a key, and hand back the one copy of its secret there will be.

	The plaintext is returned here and stored nowhere. A key somebody has lost
	is a key they replace — which is a row, and takes nothing else with it.
	"""
	from .remote import deny

	deny(folder, _("A folder on another server cannot be served from here."))
	if folder:
		frappe.get_doc("File", folder).check_permission("read")

	secret = secrets.token_urlsafe(SECRET_BYTES)
	doc = frappe.get_doc({
		"doctype": "Drive Access",
		"label": (label or "").strip() or _("Files"),
		"access_user": f"k{secrets.token_hex(8)}",
		"secret_hash": digest(secret),
		"folder": folder or "",
		"read_only": 1 if frappe.utils.sbool(read_only) else 0,
		"expires_on": frappe.utils.add_days(now_datetime(), cint(days)) if cint(days) else None,
		"enabled": 1,
	}).insert()

	return {
		"ok": True,
		"name": doc.name,
		"url": frappe.utils.get_url(PREFIX + "/"),
		"access_user": doc.access_user,
		# Once. The dialog says so, because a person who closes it without
		# copying has to make another key rather than being told to reset one.
		"secret": secret,
	}


@frappe.whitelist(methods=["POST"])
def revoke_share(name: str) -> dict:
	"""Turn a key off.

	Kept rather than deleted, so `last_used` still answers "what was this and
	when did anything last use it" — which is the question somebody asks a
	week after revoking the wrong one.
	"""
	doc = frappe.get_doc("Drive Access", name)
	if doc.owner != frappe.session.user:
		frappe.throw(_("That key is not yours."), frappe.PermissionError)
	doc.db_set("enabled", 0, update_modified=False)
	frappe.db.commit()
	return {"ok": True}
