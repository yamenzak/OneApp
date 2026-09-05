"""Reaching the site being imported from, and reading rows off it."""

import frappe
import json
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime
from urllib.parse import quote, urlparse


# How many rows one request asks for. Frappe's own list endpoint is happy with
# far more; this is sized so a batch commits often enough that a crash costs
# seconds of work rather than minutes.
BATCH = 200


# What a step may spend before the queue takes it away. A migration is a long
# job by nature and the alternative to a long timeout is a partial import that
# looks finished.
TIMEOUT = 60 * 60


# Every field of a source row travels, because the field map decides what is
# read and a map edited later should not need a re-fetch to see a column it did
# not ask for last time.
ALL_FIELDS = '["*"]'


def _endpoint(source) -> str:
	"""The source's base URL, checked before anything is sent to it.

	A customer types this in, which makes it the one place this feature can be
	pointed somewhere it should not go: an internal address, a metadata service,
	a neighbour's site on the same network. So it is https, it is a hostname
	rather than an address, and it is not a name that resolves inward.

	Not a substitute for the network's own rules, and not trying to be. It is
	the check that costs nothing and catches the mistake somebody makes by
	pasting the wrong thing.
	"""
	raw = (source.base_url or "").strip().rstrip("/")
	parsed = urlparse(raw)

	if parsed.scheme != "https":
		frappe.throw(_("A source has to be https. Credentials travel to it."))
	if not parsed.hostname or parsed.path or parsed.query:
		frappe.throw(_("A source is a host and nothing else, like https://old.example.com."))

	host = parsed.hostname.lower()
	if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".internal"):
		frappe.throw(_("That address is inside this network."))
	# An address rather than a name: the shapes that reach a metadata service or
	# a machine on the same subnet all look like one.
	if host.replace(".", "").replace(":", "").isdigit() or ":" in host:
		frappe.throw(_("A source is named by hostname, not by address."))

	return raw


def _get(source, path: str, params: dict) -> dict:
	"""One GET against the source, as the token's own user over there.

	`requests` rather than anything of Frappe's: this is an ordinary call to
	another site's REST API, and the framework's helpers are built for its own
	integrations with their own retry and logging opinions.
	"""
	import requests

	url = f"{_endpoint(source)}/api/{path}"
	secret = source.get_password("api_secret")
	answer = requests.get(
		url,
		params=params,
		headers={"Authorization": f"token {source.api_key}:{secret}"},
		timeout=60,
	)
	if answer.status_code == 401 or answer.status_code == 403:
		frappe.throw(_("The source refused the key. Check it is still valid over there."))
	answer.raise_for_status()
	return answer.json()


@frappe.whitelist()
def verify(source: str) -> dict:
	"""Ask the source who we are to it, and remember the answer.

	Worth its own button and its own field. An import runs as this user on the
	other site, so a key made from an account with half the permissions imports
	half the data and nothing anywhere says why — the rows it could not read
	simply were not in the answer.
	"""
	doc = frappe.get_doc("Import Source", source)
	doc.check_permission("write")

	try:
		who = _get(doc, "method/frappe.auth.get_logged_user", {}).get("message") or ""
	except Exception as raised:
		doc.db_set({"status": "Refused", "last_error": str(raised)[:500]})
		frappe.db.commit()
		return {"ok": False, "error": str(raised)}

	doc.db_set({
		"status": "Verified",
		"verified_as": who,
		"verified_on": now_datetime(),
		"last_error": "",
	})
	frappe.db.commit()
	return {"ok": True, "user": who}


@frappe.whitelist()
def preview(source: str, doctype: str, filters: str | None = None) -> dict:
	"""How many rows of one doctype are over there, and one of them.

	What somebody wants before writing a field map, and what the plan editor
	shows beside each step: a count to size the job, and a real row to map
	against rather than a memory of the schema.
	"""
	doc = frappe.get_doc("Import Source", source)
	doc.check_permission("read")

	params = {"limit_page_length": 1, "fields": ALL_FIELDS, "order_by": "modified desc"}
	if filters:
		params["filters"] = filters

	rows = _get(doc, f"resource/{doctype}", params).get("data") or []
	count = _get(doc, "method/frappe.client.get_count",
	             {"doctype": doctype, **({"filters": filters} if filters else {})})
	return {"count": count.get("message"), "row": rows[0] if rows else None}


def fetch(source, doctype: str, filters: list, start: int, length: int) -> list[dict]:
	"""One page of a doctype, oldest change first.

	`modified asc` is not a preference. The watermark is only safe if rows
	arrive in the order it advances through, and a page ordered any other way
	leaves a run that stops early having skipped rows it will never ask for
	again.
	"""
	return _get(source, f"resource/{doctype}", {
		"fields": ALL_FIELDS,
		"filters": json.dumps(filters),
		"order_by": "modified asc",
		"limit_start": start,
		"limit_page_length": length,
	}).get("data") or []


def attachments(source, doctype: str, name: str) -> list[dict]:
	"""What is attached to one record on the source.

	The half of a migration that gets forgotten and is the half people notice.
	Their eighty-two projects carry fifty architectural perspectives between
	them, their parties carry logos, their employees carry photographs and
	every compliance document is a scan of the paper — nine hundred and sixty
	files, and a system that arrives without them is a database rather than the
	company's records.
	"""
	return _get(source, "resource/File", {
		"fields": '["name","file_name","file_url","is_private"]',
		"filters": json.dumps([
			["attached_to_doctype", "=", doctype],
			["attached_to_name", "=", name],
		]),
		"limit_page_length": 0,
	}).get("data") or []


def download(source, file_url: str) -> bytes:
	"""One file's content, as the token's own user over there.

	A private file is only readable with the key, which is the whole reason
	this goes through the API rather than fetching the URL: half of what these
	people keep — passports, trade licences, signed invoices — is private, and
	an import that silently brought across only the public half would be worse
	than one that brought none.
	"""
	import requests

	answer = requests.get(
		f"{_endpoint(source)}{file_url}",
		headers={"Authorization": f"token {source.api_key}:{source.get_password('api_secret')}"},
		timeout=120,
	)
	answer.raise_for_status()
	return answer.content


def whole(source, doctype: str, name: str) -> dict:
	"""One document with its child tables.

	Frappe's list endpoint answers columns, and a child table is not a column —
	`fields=["*"]` on a list of quotations returns every one of them without a
	single line on it. So a step that maps child rows reads its rows twice: the
	list for the page and the watermark, then the document for what is inside
	it.

	One request per row, which is why it happens only where a step says it
	needs to: it is the difference between five quotations and twenty thousand
	attendance records.
	"""
	return _get(source, f"resource/{doctype}/{quote(str(name))}", {}).get("data") or {}
