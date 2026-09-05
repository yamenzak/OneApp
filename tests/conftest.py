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
			# Keyed `(doctype, fieldname)` rather than by the filters as well:
			# a test that wants one answer out of `get_value` wants it for the
			# one lookup its code makes, and matching a filter dict exactly
			# turns every such test into a transcription of the query.
			self.values = {}
			self.writes = []
			self.rollbacks = []
			self.savepoints = []
			self.released = []
			self.defaults = {}

		def commit(self):
			self.commits += 1

		def rollback(self, save_point=None):
			self.rollbacks.append(save_point)

		# Savepoints, as the engine uses them: one per row, so a row that will
		# not save is undone without taking the page with it. Recorded rather
		# than simulated — what a test wants to know is that the failing row
		# was rolled back to its own mark and no further.
		def savepoint(self, save_point):
			self.savepoints.append(save_point)

		def release_savepoint(self, save_point):
			self.released.append(save_point)

		def get_single_value(self, doctype, field):
			return self.singles.get((doctype, field))

		def exists(self, doctype, name=None):
			return self.records.get((doctype, name if isinstance(name, str) else None))

		def get_value(self, doctype=None, filters=None, fieldname=None, *a, **k):
			# Frappe takes a list of fieldnames and answers a list of values.
			# Keyed as a tuple so a test can say what a multi-field lookup
			# returns without the list making the key unhashable.
			key = tuple(fieldname) if isinstance(fieldname, list) else fieldname
			return self.values.get((doctype, key))

		def count(self, *a, **k):
			return 0

		def sql(self, *a, **k):
			return self.sql_result

		sql_result = [[0]]

		# Frappe's user defaults: a `DefaultValue` row per key, read on every
		# request. Real here rather than stubbed to None, because the thing
		# using them — the mail read-receipt list — is about what happens to a
		# value that keeps growing, and a store that forgets proves nothing.
		def get_default(self, key, parent=None):
			return self.defaults.get(key)

		def set_default(self, key, value, parent=None, parenttype=None):
			self.defaults[key] = value

		def set_value(self, doctype=None, name=None, field=None, value=None, **k):
			self.writes.append((doctype, name, field, value))
			return None

	# Frappe's own `_dict`: a dict that also answers to attribute access, which
	# is what every `get_all` row is. Real here because the code under test
	# reads rows as `row.name`, and a stub handing back plain dicts would fail
	# on correct code and pass on code that reads them the wrong way.
	class _Dict(dict):
		def __getattr__(self, key):
			try:
				return self[key]
			except KeyError:
				return None

		def __setattr__(self, key, value):
			self[key] = value

	frappe._dict = _Dict

	frappe.db = _DB()

	# `frappe.defaults` — the per-user half of the same store. Real rather than
	# stubbed to None for the reason the db defaults are: what uses it is a list
	# that grows, and a store that forgets what was written proves nothing.
	class _Defaults:
		def __init__(self):
			self.store = {}

		def get_user_default(self, key, user=None):
			return self.store.get((key, user))

		def set_user_default(self, key, value, user=None, parenttype=None):
			self.store[(key, user)] = value

	frappe.defaults = _Defaults()
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
	# Frappe's own: one field off one document, cached. Answers nothing by
	# default; the tests that are about a company's own settings say what it
	# holds. A stub that read `frappe.db.values` would make every such test a
	# transcription of the query rather than a statement about the answer.
	frappe.get_cached_value = lambda *a, **k: None
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
	# `frappe.utils` is a real package in the framework and a plain module here,
	# so a submodule import — `from frappe.utils.momentjs import …`, which
	# `oneapp_core/workspace.py` does for the timezone list — fails with "not a
	# package" unless it is given a module of its own.
	momentjs = types.ModuleType("frappe.utils.momentjs")
	momentjs.get_all_timezones = lambda: ["UTC", "Asia/Dubai"]
	utils.momentjs = momentjs

	# The site's own secret, used here for the HMAC that binds a direct upload
	# to the person who started it. A fixed value rather than a random one, so a
	# test can say what a forged token does not match.
	password = types.ModuleType("frappe.utils.password")
	password.get_encryption_key = lambda: "test-encryption-key"
	utils.password = password

	# The one framework module our own code borrows a renderer from: a template
	# is Jinja with the document in scope, and `get_email_template` is where
	# that contract lives. Stubbed as a module so a test can replace the
	# function; the real one needs a database.
	email = types.ModuleType("frappe.email")
	doctype = types.ModuleType("frappe.email.doctype")
	holder = types.ModuleType("frappe.email.doctype.email_template")
	rendering = types.ModuleType("frappe.email.doctype.email_template.email_template")
	rendering.get_email_template = lambda name, doc: {"subject": "", "message": ""}
	holder.email_template = rendering
	doctype.email_template = holder
	email.doctype = doctype
	frappe.email = email
	sys.modules["frappe.email"] = email
	sys.modules["frappe.email.doctype"] = doctype
	sys.modules["frappe.email.doctype.email_template"] = holder
	sys.modules["frappe.email.doctype.email_template.email_template"] = rendering

	utils.now_datetime = lambda: None
	utils.add_to_date = lambda *a, **k: None
	utils.get_datetime = lambda x: x
	# Enough of a date to be told apart from a timestamp with microseconds in it,
	# which is the whole point of the caller: a reply's attribution line.
	utils.format_datetime = lambda value, fmt=None: str(value)
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
	# Real for the same reason `getdate` is: the compliance register's whole
	# rule is "is this date inside a window of N days", and a stub that answered
	# None would make every window empty and every test pass for nothing.
	utils.add_days = lambda value, days: getdate(value) + __import__("datetime").timedelta(
		days=int(days or 0)
	)
	utils.nowdate = lambda: str(getdate())
	utils.flt = float
	# Frappe's own "an int, whatever this is" — an empty string, None and a
	# string of digits all become a number, which is why every counter in the
	# codebase goes through it rather than `int()`.
	utils.cint = lambda v=0, default=0: int(float(v)) if str(v or "").strip() else default
	utils.get_fullname = lambda u: u
	# Frappe's own. Real rather than a passthrough: what uses it is the
	# attribution line above a quoted reply, and a stub that returned its
	# argument would let a sender's display name close the paragraph it sits in.
	utils.escape_html = lambda text: (
		str(text or "")
		.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
		.replace("'", "&#39;")
	)
	# The real one drops tags and unescapes entities. A stub that only had to be
	# *shaped* right would return the argument, and then every test of "a row
	# says its sentence without markup" would pass on markup.
	utils.strip_html = lambda v: re.sub(r"<[^>]*>", "", str(v or ""))
	utils.get_url = lambda *a, **k: "https://space.localhost"
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

	# `frappe.utils.number_format`. Frappe's own table of what each number
	# format means — `#,###.##` is two decimals, a dot and a comma — with the
	# three formats a UAE site could plausibly be on. Real values, because the
	# thing being tested is that money follows this table and not the float
	# precision, and a made-up table would prove neither.
	number_format = types.ModuleType("frappe.utils.number_format")

	class NumberFormat:
		def __init__(self, precision, decimal_separator, thousands_separator, string):
			self.precision = precision
			self.decimal_separator = decimal_separator
			self.thousands_separator = thousands_separator
			self.string = string

		@classmethod
		def from_string(cls, said):
			decimal, thousands, precision = number_format.NUMBER_FORMAT_MAP[said]
			return cls(precision, decimal, thousands, said)

	number_format.NUMBER_FORMAT_MAP = {
		"#,###.##": (".", ",", 2),
		"#.###,##": (",", ".", 2),
		"# ###.##": (".", " ", 2),
		"#,##,###.##": (".", ",", 2),
		"#,###.###": (".", ",", 3),
		"#,###": ("", ",", 0),
		"#.###": ("", ".", 0),
	}
	number_format.NumberFormat = NumberFormat
	utils.number_format = number_format

	# `frappe.model.workflow`. The whole workflow engine is the framework's —
	# `apply_workflow` finds the transition, refuses a self-approval, writes the
	# state, runs the tasks and calls save/submit/cancel — so what a stub needs
	# to offer is the shape `docflow` imports, and the one exception it catches.
	workflow = types.ModuleType("frappe.model.workflow")

	class WorkflowStateError(ValidationError):
		"""Raised for a record with no workflow state yet, which is ordinary on
		one created before the workflow existed."""

	workflow.WorkflowStateError = WorkflowStateError
	workflow.get_workflow_name = lambda doctype: ""
	workflow.get_workflow = lambda doctype: None
	workflow.get_transitions = lambda doc, workflow=None, raise_exception=False: []
	workflow.apply_workflow = lambda doc, action: doc

	# `frappe.email` — the two classes `oneapp_core/email/folders.py` subclasses
	# so a connected mailbox's folders survive the sync. Stubs with no behaviour
	# on purpose: what is ours in that file is which folder a message came from
	# and whether a Sent folder is exempt from the sender check, and both are
	# testable without an IMAP session. The MIME parsing underneath is the
	# framework's and is not what these tests are about.
	email_pkg = types.ModuleType("frappe.email")
	receive = types.ModuleType("frappe.email.receive")

	class InboundMail:
		def __init__(self, content, email_account, uid=None, seen_status=None, append_to=None):
			self.content = content
			self.email_account = email_account
			self.uid = uid
			self.seen_status = seen_status
			self.append_to = append_to
			# Frappe's own: an inbox must not import your own sent mail back.
			# True by default here so the override that turns it off inside a
			# Sent folder is testing something.
			self.same = True

		def is_sender_same_as_receiver(self):
			return self.same

		def as_dict(self):
			return {"sent_or_received": "Received", "seen": self.seen_status or 0}

	receive.InboundMail = InboundMail
	email_pkg.receive = receive

	email_doctype = types.ModuleType("frappe.email.doctype")
	account_pkg = types.ModuleType("frappe.email.doctype.email_account")
	account_mod = types.ModuleType("frappe.email.doctype.email_account.email_account")

	class EmailAccount:
		def get_inbound_mails(self):
			return []

	account_mod.EmailAccount = EmailAccount

	return frappe, model, document, utils, (
		desk, desk_doctype, log_pkg, log, desk_notifications, workflow,
		number_format, email_pkg, receive, email_doctype, account_pkg, account_mod,
	)


@pytest.fixture(autouse=True)
def stub_frappe(monkeypatch):
	frappe, model, document, utils, desk = _make_frappe()
	monkeypatch.setitem(sys.modules, "frappe", frappe)
	monkeypatch.setitem(sys.modules, "frappe.model", model)
	monkeypatch.setitem(sys.modules, "frappe.model.document", document)
	monkeypatch.setitem(sys.modules, "frappe.utils", utils)
	monkeypatch.setitem(sys.modules, "frappe.utils.momentjs", utils.momentjs)
	monkeypatch.setitem(sys.modules, "frappe.utils.password", utils.password)
	for module in desk:
		monkeypatch.setitem(sys.modules, module.__name__, module)
	yield frappe

	# Modules imported against the stub must not leak into the next test.
	for name in list(sys.modules):
		if name.startswith(("oneapp_control", "oneapp.")):
			del sys.modules[name]


def _package_stubber(monkeypatch, package):
	"""Replace a name in every module of a layered package that uses it.

	These packages are layered modules, and each imports the helpers it needs
	*by name* — so `monkeypatch.setattr(package, "_resolve")` rebinds the
	re-export and reaches nobody: the layer that uses it goes on calling the
	real one, and the test passes for the wrong reason or fails for a confusing
	one.

	This walks the submodules and replaces the name in each that has it, so a
	test says what it means and keeps meaning it the next time the layering
	moves.
	"""
	from types import ModuleType

	def stub(name, value):
		found = 0
		for holder in [package, *vars(package).values()]:
			if holder is not package and not (
				isinstance(holder, ModuleType)
				and getattr(holder, "__name__", "").startswith(package.__name__ + ".")
			):
				continue
			if hasattr(holder, name):
				monkeypatch.setattr(holder, name, value)
				found += 1
		assert found, f"nothing in {package.__name__} is called {name!r}"
		return value

	return stub


@pytest.fixture
def stub_spaceview(monkeypatch):
	"""Stub a name across the screen package. See `_package_stubber`."""
	from oneapp.oneapp_core import spaceview

	return _package_stubber(monkeypatch, spaceview)


@pytest.fixture
def stub_mailbox(monkeypatch):
	"""Stub a name across the mail package. See `_package_stubber`."""
	from oneapp.oneapp_core.email import mailbox

	return _package_stubber(monkeypatch, mailbox)


@pytest.fixture
def stub_importer(monkeypatch):
	"""Stub a name across the import package. See `_package_stubber`."""
	from oneapp.oneapp_core import importer

	return _package_stubber(monkeypatch, importer)
