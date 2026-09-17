"""What we change about somebody else's app, held to what we actually do.

`docs/CLEANUP.md` stage 10. `oneapp/adapters/` is three declarations — one per
foreign app — saying which of their doctypes we subclass, which we hook, which
we add fields to and which of their functions we call. Nothing imports them at
runtime. They are worth having only if they cannot be wrong, and that is this
file.

**Both directions, and the second is the one that earns it.** An adapter
describing a seam that no longer exists is a stale document, which is bad.
A seam that exists and is described nowhere is the thing being fixed: adding a
`doc_events` entry on `Sales Invoice` is two lines in `hooks.py`, and before
this it was invisible to anybody asking what we do to ERPNext.

The sources are `hooks.py` (parsed, never imported — it wants a bench), the
space manifests in `oneapp_control/spaces/`, and an AST scan of every module in
the app.
"""

import ast
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "apps/oneapp/oneapp"
HOOKS = APP / "hooks.py"

sys.path.insert(0, str(ROOT / "apps/oneapp"))
sys.path.insert(0, str(ROOT / "apps/oneapp_control"))

from oneapp import adapters  # noqa: E402
from oneapp_control import spaces  # noqa: E402

APPS = sorted(adapters.ADAPTERS)


def _hooks(name: str):
	"""One table out of `hooks.py`, parsed rather than imported."""
	tree = ast.parse(HOOKS.read_text())
	for node in tree.body:
		if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
			return ast.literal_eval(node.value)
	raise AssertionError(f"{name} is gone from hooks.py")


OVERRIDES = _hooks("override_doctype_class")
EVENTS = _hooks("doc_events")


def _ours() -> set[str]:
	"""Every doctype this repository declares, read off the checked-in JSON.

	What is left after removing these from the hook tables is, by definition,
	somebody else's — which is what an adapter has to account for.
	"""
	found = set()
	for path in ROOT.glob("apps/*/*/*/doctype/*/*.json"):
		try:
			doc = json.loads(path.read_text())
		except (ValueError, UnicodeDecodeError):
			continue
		if isinstance(doc, dict) and doc.get("doctype") == "DocType":
			found.add(doc["name"])
	return found


OURS = _ours()

#: The one key in `doc_events` that is not a doctype. It is declared in the
#: Frappe adapter's `HOOKED` like any other, because six handlers on every
#: doctype in the site is the heaviest thing in that table and the last thing
#: that should be exempt from being written down.
EVERY = "*"


def _extended() -> dict[str, set[str]]:
	"""Every foreign doctype a space manifest adds a field to, and which
	spaces asked. Assembled rather than listed — the manifests are the
	declaration and the adapters are the read-back."""
	found = {}
	for code, module in spaces.SPACES.items():
		for row in getattr(module, "CUSTOM_FIELDS", None) or []:
			found.setdefault(row["dt"], set()).add(code)
	return found


EXTENDED = _extended()


def _imported() -> dict[str, set[str]]:
	"""Every name the app imports out of another app, and from where."""
	found = {}
	for path in sorted(APP.rglob("*.py")):
		if "__pycache__" in str(path):
			continue
		try:
			tree = ast.parse(path.read_text())
		except SyntaxError:
			continue
		where = str(path.relative_to(APP))
		for node in ast.walk(tree):
			if isinstance(node, ast.ImportFrom) and node.module:
				if node.module.split(".")[0] not in APPS:
					continue
				for alias in node.names:
					found.setdefault(f"{node.module}.{alias.name}", set()).add(where)
			elif isinstance(node, ast.Import):
				for alias in node.names:
					if alias.name.split(".")[0] in APPS:
						found.setdefault(alias.name, set()).add(where)
	return found


IMPORTED = _imported()


# --------------------------------------------------------------------------- #
# A. The readers found something
#
# Every rule below passes if its source came back empty, so each one is stated
# first.
# --------------------------------------------------------------------------- #

def test_the_readers_found_something():
	assert len(APPS) == 3, APPS
	assert len(OURS) >= 80, len(OURS)
	assert len(OVERRIDES) >= 5, OVERRIDES
	assert len(EVENTS) >= 15, sorted(EVENTS)
	assert len(EXTENDED) >= 15, sorted(EXTENDED)
	assert len(IMPORTED) >= 15, len(IMPORTED)


@pytest.mark.parametrize("app", APPS)
def test_every_adapter_declares_all_four(app):
	module = adapters.ADAPTERS[app]
	for table in ("SUBCLASSED", "HOOKED", "EXTENDED", "CALLED"):
		assert hasattr(module, table), f"{app} has no {table}"
		assert isinstance(getattr(module, table), dict)


@pytest.mark.parametrize("app", APPS)
def test_every_entry_says_why(app):
	"""A table of doctype names with no reasons is a list somebody could have
	grepped. The reason is the whole content.

	`EXTENDED` is the exception and is checked by the rule below instead: the
	question there is *which space asked*, and "RUA." is a complete answer to
	it. Demanding a sentence would get one written to satisfy this.
	"""
	module = adapters.ADAPTERS[app]
	for table in ("SUBCLASSED", "HOOKED", "CALLED"):
		for key, why in getattr(module, table).items():
			assert isinstance(why, str) and len(why.split()) >= 3, (
				f"{app}.{table}[{key!r}] says {why!r}"
			)


#: What a space is called in prose, where that differs from its code.
#: `CLAUDE.md`: an id is not a name, and four of them disagree on purpose.
SPOKEN = {"onehr": "OnePeople", "onebook": "OneBook", "onecrm": "OneCRM",
          "oneproject": "OneProject", "onemobility": "OneMobility",
          "rua": "RUA"}


@pytest.mark.parametrize("app", APPS)
def test_every_extension_names_the_space_that_asked(app):
	"""The one question somebody has when they find a `custom_` column they
	did not expect. Checked against the manifests rather than against a word
	count, so a field moving between spaces fails here."""
	for doctype, why in adapters.ADAPTERS[app].EXTENDED.items():
		for code in sorted(EXTENDED.get(doctype, ())):
			assert SPOKEN.get(code, code) in why, (
				f"{app}.EXTENDED[{doctype!r}] does not name {code}, which "
				f"extends it"
			)


# --------------------------------------------------------------------------- #
# B. Every seam is described
# --------------------------------------------------------------------------- #

def test_every_foreign_controller_we_replace_is_declared():
	foreign = {dt for dt in OVERRIDES if dt not in OURS}
	declared = {dt for module in adapters.ADAPTERS.values()
	            for dt in module.SUBCLASSED}
	assert foreign <= declared, (
		f"hooks.py replaces the controller of {sorted(foreign - declared)} and "
		f"no adapter says so"
	)


def test_every_foreign_doctype_we_hook_is_declared():
	foreign = {dt for dt in EVENTS if dt not in OURS}
	declared = {dt for module in adapters.ADAPTERS.values()
	            for dt in module.HOOKED}
	assert foreign <= declared, (
		f"hooks.py hooks {sorted(foreign - declared)} and no adapter says so"
	)


def test_every_foreign_doctype_we_extend_is_declared():
	foreign = {dt for dt in EXTENDED if dt not in OURS}
	declared = {dt for module in adapters.ADAPTERS.values()
	            for dt in module.EXTENDED}
	assert foreign == declared, (
		f"manifests extend {sorted(foreign - declared)} and no adapter says "
		f"so; adapters claim {sorted(declared - foreign)} nothing extends"
	)


def test_every_foreign_function_we_import_is_declared():
	"""The direction that bites hardest on an upgrade: a dotted path into
	somebody else's app is a string until it is not there any more."""
	declared = {name for module in adapters.ADAPTERS.values()
	            for name in module.CALLED}
	# `frappe.*` is the platform, not a seam — the Frappe adapter says where
	# that line is. Only the paths it names are checked, in the other
	# direction; ERPNext and HRMS are checked whole, because every import of
	# theirs is a decision.
	wanted = {name for name in IMPORTED
	          if name.split(".")[0] in ("erpnext", "hrms")}
	assert wanted <= declared, (
		f"the app imports {sorted(wanted - declared)} and no adapter says why"
	)


# --------------------------------------------------------------------------- #
# C. And nothing is described that is not there
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("app", APPS)
def test_an_adapter_claims_no_controller_we_do_not_replace(app):
	for dt in adapters.ADAPTERS[app].SUBCLASSED:
		assert dt in OVERRIDES, (
			f"{app} says we subclass {dt} and hooks.py does not"
		)


@pytest.mark.parametrize("app", APPS)
def test_an_adapter_claims_no_hook_we_do_not_have(app):
	for dt in adapters.ADAPTERS[app].HOOKED:
		assert dt in EVENTS, f"{app} says we hook {dt} and hooks.py does not"


@pytest.mark.parametrize("app", APPS)
def test_an_adapter_claims_no_function_we_do_not_call(app):
	for name in adapters.ADAPTERS[app].CALLED:
		assert name in IMPORTED, (
			f"{app} says we call {name} and nothing in the app imports it"
		)


@pytest.mark.parametrize("app", APPS)
def test_an_adapter_names_no_doctype_of_ours(app):
	"""A doctype this repository declares is not a seam. Naming one here would
	be describing our own schema as somebody else's change."""
	claimed = adapters.touched(adapters.ADAPTERS[app])
	assert not (claimed & OURS), sorted(claimed & OURS)


def test_no_doctype_belongs_to_two_apps():
	"""`owner_of` has no sensible tiebreak, so the answer is that this must not
	happen."""
	seen = {}
	for app, module in adapters.ADAPTERS.items():
		for dt in adapters.touched(module):
			assert dt not in seen, f"{dt} is claimed by {seen[dt]} and {app}"
			seen[dt] = app


# --------------------------------------------------------------------------- #
# D. The witnesses
# --------------------------------------------------------------------------- #

def test_an_undescribed_hook_would_be_caught():
	foreign = {dt for dt in list(EVENTS) + ["Stock Entry"] if dt not in OURS}
	declared = {dt for module in adapters.ADAPTERS.values()
	            for dt in module.HOOKED}
	assert not foreign <= declared


def test_an_undescribed_import_would_be_caught():
	declared = {name for module in adapters.ADAPTERS.values()
	            for name in module.CALLED}
	assert "erpnext.stock.get_item_details.get_item_details" not in declared


def test_the_ours_reader_knows_our_own_doctypes():
	"""If this started matching nothing, every doctype would read as foreign
	and the completeness rules would demand adapters for our own tables."""
	assert "OneSpace Space" in OURS
	assert "Transit Source" in OURS
	assert "Sales Invoice" not in OURS
