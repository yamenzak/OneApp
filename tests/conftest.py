"""Test the pure logic without a bench.

Most of what can silently go wrong here — signature verification, slug rules,
retry backoff, Stripe's form encoding — is ordinary Python that happens to live
inside a Frappe app. Stubbing `frappe` lets that logic be tested in CI on every
push, rather than only on a machine with MariaDB, Redis and a built site.

Anything genuinely needing the ORM belongs in Frappe's own test runner instead.
"""

import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "oneapp_control"))
sys.path.insert(0, str(ROOT / "apps" / "oneapp"))


class ValidationError(Exception):
	pass


class PermissionError_(Exception):
	pass


class DoesNotExistError(ValidationError):
	"""Frappe's own, and a subclass of ValidationError there too.

	Raised by `get_meta` for a name that is not a doctype — which happens in
	ordinary use: a Version row is written against `Series` when a naming
	counter moves, and Series is not a doctype.
	"""


def _make_frappe():
	frappe = types.ModuleType("frappe")

	frappe.ValidationError = ValidationError
	frappe.PermissionError = PermissionError_
	frappe.DoesNotExistError = DoesNotExistError

	def throw(msg, exc=None, *args, **kwargs):
		raise (exc or ValidationError)(str(msg))

	frappe.throw = throw
	frappe._ = lambda s: s
	frappe.request = None
	frappe.get_hooks = lambda key, *a, **kw: []
	frappe.get_module = __import__
	frappe.parse_json = lambda v: __import__("json").loads(v) if isinstance(v, str) else v
	frappe.session = types.SimpleNamespace(user="Administrator")
	# The flags a request carries. Empty by default, which is what an ordinary
	# request looks like — the code that reads them is guarding against installs,
	# migrations and patches, and every one of those is set by Frappe itself.
	frappe.flags = types.SimpleNamespace()

	class _DB:
		def __init__(self):
			self.singles = {}
			self.records = {}
			self.commits = 0

		def commit(self):
			self.commits += 1

		def get_single_value(self, doctype, field):
			return self.singles.get((doctype, field))

		def exists(self, doctype, name=None):
			return self.records.get((doctype, name if isinstance(name, str) else None))

		def get_value(self, *a, **k):
			return None

		def count(self, *a, **k):
			return 0

		def sql(self, *a, **k):
			return self.sql_result

		sql_result = [[0]]

		def set_value(self, *a, **k):
			return None

	frappe.db = _DB()
	frappe.sql = frappe.db.sql

	class _Cache:
		def __init__(self):
			self.store = {}

		def get_value(self, key, *a, **k):
			return self.store.get(key)

		def set_value(self, key, value, **k):
			self.store[key] = value

		def delete_value(self, key):
			self.store.pop(key, None)

	_cache = _Cache()
	frappe.cache = lambda: _cache
	frappe.conf = {}
	frappe.get_all = lambda *a, **k: []
	frappe.get_doc = lambda *a, **k: None
	frappe.get_single = lambda *a, **k: None
	frappe.get_cached_doc = lambda *a, **k: None
	frappe.log_error = lambda **k: None
	frappe.get_roles = lambda *a: []
	frappe.generate_hash = lambda length=10: "0" * length
	# Frappe's own behaviour: parse a string, pass anything else through. An
	# identity stub reads a JSON array as a string, which fails where the fake
	# is thin rather than where the code is wrong.
	def parse_json(value):
		if isinstance(value, str | bytes):
			return __import__("json").loads(value)
		return value

	frappe.parse_json = parse_json
	# Frappe's own, near enough: it serialises with a default that stringifies
	# dates. A plain `json.dumps` raises on the datetimes that turn up in a
	# lifecycle detail block, which would fail in the test and not in production.
	frappe.as_json = lambda value, **k: __import__("json").dumps(value, default=str)
	frappe.get_traceback = lambda *a, **k: ""
	# Frappe's own: drop whatever it queued to show the user. Called where a
	# raise was caught and answered rather than reported — a `get_meta` for a
	# `ref_doctype` that is not a doctype, a series template that cannot be
	# previewed without a document.
	frappe.clear_last_message = lambda: None

	def get_attr(path):
		"""Frappe's own: import the module and take the last attribute."""
		module, _, attribute = str(path).rpartition(".")
		return getattr(__import__(module, fromlist=[attribute]), attribute)

	frappe.get_attr = get_attr
	# Permissive by default, and overridden by the tests that are about
	# permission. A stub that refused everything would make every unrelated test
	# assert its own workaround.
	frappe.has_permission = lambda *a, **k: True

	def whitelist(*d_args, **d_kwargs):
		"""Passthrough decorator — routing is Frappe's job, not the logic's."""
		def decorator(fn):
			return fn

		if len(d_args) == 1 and callable(d_args[0]) and not d_kwargs:
			return d_args[0]
		return decorator

	frappe.whitelist = whitelist

	utils = types.ModuleType("frappe.utils")
	utils.now_datetime = lambda: None
	utils.add_to_date = lambda *a, **k: None
	utils.get_datetime = lambda x: x
	# Real, not a stub returning None: the AI pricer picks between two rows by
	# comparing today against a rate's effective window, and a getdate that
	# answers None makes every dated rate look current.
	def getdate(value=None):
		import datetime

		if value is None:
			return datetime.date.today()
		if isinstance(value, datetime.datetime):
			return value.date()
		if isinstance(value, datetime.date):
			return value
		return datetime.date.fromisoformat(str(value)[:10])

	utils.getdate = getdate
	utils.today = lambda: str(getdate())
	utils.flt = float
	utils.get_fullname = lambda u: u
	# The real one drops tags and unescapes entities. A stub that only had to be
	# *shaped* right would return the argument, and then every test of "a row
	# says its sentence without markup" would pass on markup.
	utils.strip_html = lambda v: re.sub(r"<[^>]*>", "", str(v or ""))
	frappe.utils = utils

	model = types.ModuleType("frappe.model")
	document = types.ModuleType("frappe.model.document")

	class Document:
		pass

	document.Document = Document
	model.document = document
	# The framework's own set of "this doctype is a record of what happened".
	# Real names, because `followable` excludes them and a test that used an
	# invented one would prove nothing about the list production uses.
	model.log_types = (
		"Version",
		"Error Log",
		"Scheduled Job Log",
		"Activity Log",
		"Route History",
	)

	# Bold is markup, and the panel strips markup — so a producer that formats
	# with it and a reader that removes it are one round trip in the tests.
	frappe.bold = lambda value: f"<b>{value}</b>"

	# Meta, thin: what the follow producer asks of it is `track_changes` and a
	# field's label. Tests set `frappe._meta` to say what a doctype is.
	def get_meta(doctype):
		return frappe._meta.get(doctype) or types.SimpleNamespace(
			track_changes=0, get_field=lambda name: None
		)

	frappe._meta = {}
	frappe.get_meta = get_meta

	# The framework's notification producer, as a module rather than a function,
	# because `sync.sync_notices` imports it by path — and a `from a.b.c import
	# d` needs every parent in `sys.modules` when `a` is not a real package.
	desk = types.ModuleType("frappe.desk")
	desk_doctype = types.ModuleType("frappe.desk.doctype")
	log_pkg = types.ModuleType("frappe.desk.doctype.notification_log")
	log = types.ModuleType("frappe.desk.doctype.notification_log.notification_log")
	log.enqueue_create_notification = lambda users, doc, dedupe_on=None: None
	log.get_skip_email_types = lambda: set()
	log.get_title = lambda doctype, name, title_field=None: name
	log.get_title_html = lambda title: f'<b class="subject-title">{title}</b>'

	# `frappe.desk.notifications`, for the mention extractor the follow producer
	# uses to avoid telling somebody about a comment twice.
	desk_notifications = types.ModuleType("frappe.desk.notifications")
	desk_notifications.extract_mentions = lambda txt: re.findall(
		r'data-id="([^"]+)"', str(txt or "")
	)

	return frappe, model, document, utils, (
		desk, desk_doctype, log_pkg, log, desk_notifications,
	)


@pytest.fixture(autouse=True)
def stub_frappe(monkeypatch):
	frappe, model, document, utils, desk = _make_frappe()
	monkeypatch.setitem(sys.modules, "frappe", frappe)
	monkeypatch.setitem(sys.modules, "frappe.model", model)
	monkeypatch.setitem(sys.modules, "frappe.model.document", document)
	monkeypatch.setitem(sys.modules, "frappe.utils", utils)
	for module in desk:
		monkeypatch.setitem(sys.modules, module.__name__, module)
	yield frappe

	# Modules imported against the stub must not leak into the next test.
	for name in list(sys.modules):
		if name.startswith(("oneapp_control", "oneapp.")):
			del sys.modules[name]
