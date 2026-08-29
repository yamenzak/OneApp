"""Test the pure logic without a bench.

Most of what can silently go wrong here — signature verification, slug rules,
retry backoff, Stripe's form encoding — is ordinary Python that happens to live
inside a Frappe app. Stubbing `frappe` lets that logic be tested in CI on every
push, rather than only on a machine with MariaDB, Redis and a built site.

Anything genuinely needing the ORM belongs in Frappe's own test runner instead.
"""

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


def _make_frappe():
	frappe = types.ModuleType("frappe")

	frappe.ValidationError = ValidationError
	frappe.PermissionError = PermissionError_

	def throw(msg, exc=None, *args, **kwargs):
		raise (exc or ValidationError)(str(msg))

	frappe.throw = throw
	frappe._ = lambda s: s
	frappe.request = None
	frappe.session = types.SimpleNamespace(user="Administrator")

	class _DB:
		def __init__(self):
			self.singles = {}
			self.records = {}

		def get_single_value(self, doctype, field):
			return self.singles.get((doctype, field))

		def exists(self, doctype, name=None):
			return self.records.get((doctype, name if isinstance(name, str) else None))

		def get_value(self, *a, **k):
			return None

		def count(self, *a, **k):
			return 0

	frappe.db = _DB()
	frappe.get_all = lambda *a, **k: []
	frappe.get_doc = lambda *a, **k: None
	frappe.get_single = lambda *a, **k: None
	frappe.get_cached_doc = lambda *a, **k: None
	frappe.log_error = lambda **k: None
	frappe.get_roles = lambda *a: []
	frappe.generate_hash = lambda length=10: "0" * length
	frappe.parse_json = lambda x: x
	frappe.get_traceback = lambda *a, **k: ""

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
	utils.getdate = lambda *a: None
	utils.flt = float
	utils.get_fullname = lambda u: u
	frappe.utils = utils

	model = types.ModuleType("frappe.model")
	document = types.ModuleType("frappe.model.document")

	class Document:
		pass

	document.Document = Document
	model.document = document

	return frappe, model, document, utils


@pytest.fixture(autouse=True)
def stub_frappe(monkeypatch):
	frappe, model, document, utils = _make_frappe()
	monkeypatch.setitem(sys.modules, "frappe", frappe)
	monkeypatch.setitem(sys.modules, "frappe.model", model)
	monkeypatch.setitem(sys.modules, "frappe.model.document", document)
	monkeypatch.setitem(sys.modules, "frappe.utils", utils)
	yield frappe

	# Modules imported against the stub must not leak into the next test.
	for name in list(sys.modules):
		if name.startswith(("oneapp_control", "oneapp.")):
			del sys.modules[name]
