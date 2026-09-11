"""A face on a contact, fetched once and kept here.

`onemail/people.py` says nothing leaves the site, and names Gravatar as the
thing it refuses. This is the amendment rather than a hole in it, and the
distinction is the whole design: what that rule forbade was a third-party URL
*in the page*, so that drawing a list of fifty conversations tells Gravatar
who fifty of the customer's correspondents are, on every render, from every
reader's browser. What happens here is one request from the server, the first
time a contact is saved without a picture, and the bytes are stored.

So the claims worth holding are about *when* and *how often* something leaves,
not only about what comes back.
"""

import importlib
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def faces(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp."):
			del sys.modules[name]
	return importlib.import_module("oneapp.onemail.faces"), stub_frappe


def _contact(**kw):
	row = {
		"doctype": "Contact",
		"name": "CT-1",
		"image": "",
		"email_id": "hala@alreem-consultants.ae",
		module_tried: None,
	}
	row.update(kw)
	return types.SimpleNamespace(**{k: v for k, v in row.items()}, get=row.get)


module_tried = "custom_face_tried"


# --------------------------------------------------------------------------- #
# What leaves, and how often
# --------------------------------------------------------------------------- #

def test_nothing_leaves_while_a_page_renders(faces):
	"""The rule `people.py` states, still true. Every request in this module
	is made by the server out of a background job; none of them is reachable
	from a list being drawn."""
	source = (ROOT / "apps/oneapp/oneapp/onemail/people.py").read_text()
	# The resolver that rides along with every mail row still fetches nothing.
	assert "requests" not in source
	assert "gravatar" not in source.lower().replace("no gravatar", "")


def test_a_miss_is_remembered_so_it_is_asked_once(faces):
	"""A contact with no Gravatar and no website must not be two foreign
	requests every time somebody edits their phone number."""
	module, frappe = faces
	doc = _contact()
	written = {}
	doc.db_set = lambda field, value, **k: written.__setitem__(field, value)

	frappe.db.exists = lambda *a, **k: True
	frappe.get_doc = lambda *a, **k: doc
	module._look = lambda d: None

	assert module.fetch("Contact", "CT-1") == ""
	assert module.TRIED_FIELD in written


def test_a_picture_somebody_set_is_never_overwritten(faces):
	module, _ = faces
	doc = _contact(image="/files/her-own-photo.png")
	assert module._wanted(doc) is False


def test_a_record_already_asked_about_is_not_asked_again(faces):
	module, _ = faces
	doc = _contact(**{module_tried: "2026-09-11 10:00:00"})
	assert module._wanted(doc) is False


def test_there_is_no_switch(faces):
	"""It was operator-gated for a while, beside link previews. There is no
	workspace that wants initials where a face is available, so the switch was
	a setting nobody would ever have moved — and one more thing that could be
	off when somebody wondered why a list looked plain.

	What it costs is a hash of an address and a domain to two third parties,
	once per record; the module says so where somebody writing a DPA will find
	it.
	"""
	module, _ = faces
	assert not hasattr(module, "enabled")

	bench = (ROOT / "apps/oneapp_control/oneapp_control/provisioning/bench_config.py").read_text()
	assert "contact_avatars" not in bench


# --------------------------------------------------------------------------- #
# Where a picture comes from
# --------------------------------------------------------------------------- #

def test_a_person_is_looked_up_by_a_hash_and_not_an_address(faces):
	"""Gravatar's own rule, and the reason the address itself never travels."""
	module, _ = faces
	import hashlib

	said = module._gravatar_hash("  Hala@AlReem-Consultants.AE ")
	assert said == hashlib.sha256(b"hala@alreem-consultants.ae").hexdigest()
	assert "hala" not in module.GRAVATAR.format(hash=said)


def test_a_miss_is_a_miss_and_not_a_placeholder(faces):
	"""Gravatar will happily generate an identicon and Google will hand back a
	grey globe; a procedural pattern is worse than the initials this product
	already draws. So one is asked for a 404, and the other answers 404 with
	the globe in the body — which the status check drops."""
	module, _ = faces
	assert "d=404" in module.GRAVATAR

	import inspect
	assert "status_code != 200" in inspect.getsource(module._get)


@pytest.mark.parametrize(
	"email,expected",
	[
		("hala@alreem-consultants.ae", "alreem-consultants.ae"),
		("someone@gmail.com", ""),
		("someone@outlook.com", ""),
		("someone@proton.me", ""),
		("nonsense", ""),
	],
)
def test_a_free_mail_address_is_not_an_organisation(faces, email, expected):
	"""`gmail.com` on every personal contact would be Google's envelope on a
	third of somebody's address book."""
	module, _ = faces
	assert module._domain(_contact(email_id=email)) == expected


def test_a_company_prefers_its_own_website_to_its_address(faces):
	module, _ = faces
	doc = types.SimpleNamespace(doctype="Company", name="Acme")
	row = {"company_logo": "", "email": "info@gmail.com",
	       "website": "https://www.acme.ae/about"}
	doc.get = row.get
	assert module._domain(doc) == "acme.ae"


# --------------------------------------------------------------------------- #
# The fetch itself
# --------------------------------------------------------------------------- #

def test_only_two_hosts_are_ever_talked_to(faces):
	"""A fixed pair rather than a validated URL is the whole SSRF answer here:
	nothing a customer types decides where the request goes."""
	module, _ = faces
	assert module._get("http://www.gravatar.com/avatar/x") is None
	assert module._get("https://evil.example/avatar/x") is None
	assert module.HOSTS == {"www.gravatar.com", "t3.gstatic.com"}


def test_the_two_urls_only_ever_point_at_those_hosts(faces):
	from urllib.parse import urlparse

	module, _ = faces
	for template, value in ((module.GRAVATAR, {"hash": "abc"}),
	                        (module.FAVICON, {"domain": "acme.ae"})):
		assert urlparse(template.format(**value)).hostname in module.HOSTS


def test_anything_that_is_not_a_small_image_is_dropped(faces, monkeypatch):
	module, _ = faces

	def answer(status=200, kind="image/png", body=b"x" * 10):
		reply = types.SimpleNamespace()
		reply.status_code = status
		reply.headers = {"Content-Type": kind}
		reply.raw = types.SimpleNamespace(read=lambda n, decode_content=True: body)
		return reply

	fake = types.ModuleType("requests")
	url = "https://www.gravatar.com/avatar/abc"

	fake.get = lambda *a, **k: answer(status=404)
	monkeypatch.setitem(sys.modules, "requests", fake)
	assert module._get(url) is None

	fake.get = lambda *a, **k: answer(kind="text/html")
	assert module._get(url) is None

	fake.get = lambda *a, **k: answer(body=b"x" * (module.MAX_BYTES + 1))
	assert module._get(url) is None

	fake.get = lambda *a, **k: answer()
	assert module._get(url) == (b"x" * 10, "png")


def test_the_fetch_never_raises_into_a_save(faces, monkeypatch):
	"""A contact must save whether or not Gravatar is up."""
	module, _ = faces
	fake = types.ModuleType("requests")

	def boom(*a, **k):
		raise OSError("no route to host")

	fake.get = boom
	monkeypatch.setitem(sys.modules, "requests", fake)
	assert module._get("https://www.gravatar.com/avatar/abc") is None


# --------------------------------------------------------------------------- #
# Where it lands
# --------------------------------------------------------------------------- #

def test_the_image_becomes_a_file_and_the_field_points_at_it(faces):
	"""Both, and the second is not redundant however much it looks it.

	Frappe only writes `attached_to_field` into the parent when a file url
	*changes* — not on insert. Setting the one and not the other leaves the
	picture as an attachment on the contact with nothing drawing it, which is
	how this was wrong the first time it was run against a real record.
	"""
	module, frappe = faces
	made, wrote = {}, {}
	frappe.get_doc = lambda payload: types.SimpleNamespace(
		insert=lambda **k: made.update(payload) or types.SimpleNamespace(
			file_url="/private/files/ct-1-image.png"
		)
	)

	doc = types.SimpleNamespace(doctype="Contact", name="CT-1")
	doc.db_set = lambda field, value, **k: wrote.__setitem__(field, value)
	url = module._attach(doc, "image", b"bytes", "png")

	assert url == "/private/files/ct-1-image.png"
	assert wrote == {"image": "/private/files/ct-1-image.png"}
	assert made["attached_to_doctype"] == "Contact"
	assert made["attached_to_name"] == "CT-1"
	assert made["attached_to_field"] == "image"
	# A contact's face is the workspace's business, and Frappe serves a
	# private file behind a permission check on the record it hangs off.
	assert made["is_private"] == 1


def test_the_save_does_not_wait_on_two_foreign_hosts(faces):
	"""A contact imported in a batch of four hundred must not be four hundred
	requests inside one transaction."""
	import inspect

	module, _ = faces
	source = inspect.getsource(module.on_save)
	assert "frappe.enqueue" in source
	assert "enqueue_after_commit=True" in source


def test_the_column_comes_from_the_same_table_the_hook_reads(faces):
	"""Adding `Customer` to `KINDS` must add its column too, rather than in a
	second place that can disagree."""
	module, _ = faces
	install = (ROOT / "apps/oneapp/oneapp/install.py").read_text()
	assert "for doctype in FACE_KINDS" in install

	hooks = (ROOT / "apps/oneapp/oneapp/hooks.py").read_text()
	for doctype in module.KINDS:
		assert f'"{doctype}": {{\n\t\t"after_insert": "oneapp.onemail.faces.on_save"' in hooks
