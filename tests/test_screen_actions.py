"""What a screen can do that is neither listing nor editing.

A screen over a doctype gets a list, filters, a record and a form for free. Two
things it does not: a method that is not a field write — replaying a Stripe
event, moving a workspace onto its plan's current terms — and a way through to a
bespoke screen that belongs to one record. Both used to live in hand-written
console pages, so retiring those without this would have left them doable only
in the desk, which is the one place this product does not go.

The seam is small, and its whole value is that it is an allowlist. So these are
mostly about what it refuses.
"""

import ast
from pathlib import Path

import pytest
import sources

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ROOT / "apps/oneapp_control/oneapp_control/entitlements/actions.py"


@pytest.fixture
def spaceview(stub_frappe):
	from oneapp.onespace import spaceview

	return spaceview


def declare(stub_frappe, rows):
	"""Register a provider returning `rows`, as the hook would."""
	import sys
	import types

	module = types.ModuleType("fake_actions")
	module.actions = lambda: rows
	sys.modules["fake_actions"] = module
	stub_frappe.get_hooks = lambda key, *a, **kw: (
		["fake_actions.actions"] if key == "onespace_screen_actions" else []
	)


# --------------------------------------------------------------------------- #
# What counts as an action
# --------------------------------------------------------------------------- #

def test_an_action_either_calls_or_navigates_but_not_both(spaceview, stub_frappe):
	"""A row meaning to do both is a provider bug, and the one place that can
	see it is here. Rendering it would give a button two behaviours and pick one
	by accident."""
	declare(stub_frappe, {"s/screen": [
		{"key": "both", "label": "Both", "method": "x.y", "screen": "other"},
		{"key": "neither", "label": "Neither"},
		{"key": "call", "label": "Call", "method": "x.y"},
		{"key": "go", "label": "Go", "screen": "other"},
	]})
	keys = [row["key"] for row in spaceview.actions("s", "screen")]
	assert keys == ["call", "go"]


def test_an_action_without_a_label_is_not_a_button(spaceview, stub_frappe):
	declare(stub_frappe, {"s/screen": [{"key": "x", "method": "a.b"}]})
	assert spaceview.actions("s", "screen") == []


def test_only_what_an_action_may_say_survives(spaceview, stub_frappe):
	"""The shape ends up as a button that calls a method. A provider is not a
	place to smuggle extra arguments through to the runner."""
	declare(stub_frappe, {"s/screen": [
		{"key": "x", "label": "X", "method": "a.b", "args": {"force": True}},
	]})
	assert "args" not in spaceview.actions("s", "screen")[0]


def test_the_scope_falls_back_to_one_record(spaceview, stub_frappe):
	"""And `scope` is arity, not placement: every action is rendered in both
	places and this says only how many records the verb takes. The two old
	words still resolve, because a declaration is shipped by a provider and a
	rename should not silently change what one means."""
	declare(stub_frappe, {"s/screen": [
		{"key": "x", "label": "X", "method": "a.b"},
		{"key": "y", "label": "Y", "method": "a.b", "scope": "everything"},
		{"key": "z", "label": "Z", "method": "a.b", "scope": "many"},
		{"key": "old1", "label": "O", "method": "a.b", "scope": "record"},
		{"key": "old2", "label": "O", "method": "a.b", "scope": "selection"},
	]})
	scopes = [row["scope"] for row in spaceview.actions("s", "screen")]
	assert scopes == ["one", "one", "many", "one", "many"]


def test_navigation_is_always_one_record(spaceview, stub_frappe):
	"""There is one address bar, and opening a screen "with these five" is not
	a thing it can mean."""
	declare(stub_frappe, {"s/screen": [
		{"key": "go", "label": "Go", "screen": "other", "scope": "many"},
	]})
	assert spaceview.actions("s", "screen")[0]["scope"] == "one"


def test_a_screen_action_is_given_the_parameter_it_travels_in(spaceview, stub_frappe):
	"""The target screen reads the record off the address, so the name of the
	query parameter is part of the declaration rather than a convention two files
	have to remember separately."""
	declare(stub_frappe, {"s/screen": [{"key": "x", "label": "X", "screen": "other"}]})
	assert spaceview.actions("s", "screen")[0]["param"] == "record"


def test_a_failing_provider_does_not_take_out_the_screen(spaceview, stub_frappe):
	"""One app's mistake should cost its own actions, not everybody's screen."""
	import sys
	import types

	module = types.ModuleType("broken_actions")

	def boom():
		raise RuntimeError("no")

	module.actions = boom
	sys.modules["broken_actions"] = module
	stub_frappe.get_hooks = lambda key, *a, **kw: (
		["broken_actions.actions"] if key == "onespace_screen_actions" else []
	)

	assert spaceview.actions("s", "screen") == []


def test_actions_are_keyed_to_one_screen(spaceview, stub_frappe):
	"""Two spaces can each have an `overview`, and neither has to know about the
	other — the same rule the component registry follows."""
	declare(stub_frappe, {
		"one/overview": [{"key": "a", "label": "A", "method": "x.y"}],
		"two/overview": [{"key": "b", "label": "B", "method": "x.y"}],
	})
	assert [row["key"] for row in spaceview.actions("two", "overview")] == ["b"]


# --------------------------------------------------------------------------- #
# What the runner will call
# --------------------------------------------------------------------------- #

def test_the_runner_refuses_a_method_no_screen_declares(spaceview, stub_frappe, monkeypatch, stub_spaceview):
	"""The point of the seam. Without this it is a way to POST any whitelisted
	method name on the site and have it run."""
	declare(stub_frappe, {"s/screen": [{"key": "ok", "label": "OK", "method": "a.b"}]})
	stub_spaceview("_resolve", lambda *a, **k: {"screen": "screen"})

	with pytest.raises(Exception, match="not an action"):
		spaceview.run_action("s", "screen", "oneapp_control.api.admin.suspend", "T-1")


def test_the_runner_refuses_a_screen_action(spaceview, stub_frappe, monkeypatch, stub_spaceview):
	"""Navigation is the frontend's half. A screen action carries no method, so
	asking the server to run one is asking it to call nothing."""
	declare(stub_frappe, {"s/screen": [{"key": "open", "label": "Open", "screen": "other"}]})
	stub_spaceview("_resolve", lambda *a, **k: {"screen": "screen"})

	with pytest.raises(Exception, match="not an action"):
		spaceview.run_action("s", "screen", "open", "T-1")


def test_the_runner_asks_frappe_before_it_calls_anything(spaceview, stub_frappe, monkeypatch, stub_spaceview):
	"""The same permission the save path asks for. The method guards itself as
	well — every one of these was reachable directly before this existed — so
	this narrows what may be called rather than becoming the thing that decides.
	"""
	called = []
	import sys
	import types

	module = types.ModuleType("fake_endpoint")
	module.run = lambda name: called.append(name)
	sys.modules["fake_endpoint"] = module

	declare(stub_frappe, {"s/screen": [
		{"key": "go", "label": "Go", "method": "fake_endpoint.run"},
	]})
	stub_spaceview("_resolve", lambda *a, **k: {"screen": "screen", "doctype": "Thing"}
	)
	stub_frappe.has_permission = lambda *a, **k: False

	with pytest.raises(Exception, match="cannot change"):
		spaceview.run_action("s", "screen", "go", "T-1")
	assert not called, "the method ran before the permission was checked"


def test_a_selection_runs_the_method_once_per_record(spaceview, stub_frappe, monkeypatch, stub_spaceview):
	"""A failed batch is the usual case — a handler was broken for an hour — so
	the selection scope exists. Each row is its own call, so one refusal does not
	take the rest with it silently."""
	called = []
	import sys
	import types

	module = types.ModuleType("fake_endpoint2")
	module.run = lambda name: called.append(name) or {"ok": True}
	sys.modules["fake_endpoint2"] = module

	declare(stub_frappe, {"s/screen": [
		{"key": "go", "label": "Go", "scope": "selection", "method": "fake_endpoint2.run"},
	]})
	stub_spaceview("_resolve", lambda *a, **k: {"screen": "screen", "doctype": "Thing"}
	)

	result = spaceview.run_action("s", "screen", "go", ["a", "b"])
	assert called == ["a", "b"]
	assert result["ok"]


# --------------------------------------------------------------------------- #
# What the control plane declares
# --------------------------------------------------------------------------- #

@pytest.fixture
def declared(stub_frappe) -> dict:
	"""The control plane's own declaration."""
	from oneapp_control.entitlements import actions as module

	return module.actions()


def operator_screen_names() -> set[str]:
	"""Every screen the operator Space has, list and component alike."""
	source = (
		ROOT / "apps/oneapp_control/oneapp_control/entitlements/operator.py"
	).read_text()
	names = set()
	for node in ast.walk(ast.parse(source)):
		if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in (
			"SCREENS", "COMPONENTS"
		):
			names |= {row[0] for row in ast.literal_eval(node.value)}
	return names


def test_every_declared_method_exists(declared):
	"""A dotted path is a string until something calls it, and the thing that
	calls it is a button an operator presses at the worst moment."""
	admin = sources.text(ROOT / "apps/oneapp_control/oneapp_control/api/admin.py")
	for rows in declared.values():
		for row in rows:
			if not row.get("method"):
				continue
			assert row["method"].startswith("oneapp_control.api.admin."), row["method"]
			assert f"def {row['method'].rsplit('.', 1)[1]}(" in admin, row["method"]


def test_every_declared_method_takes_one_record(declared):
	"""The runner calls `method(name)`. Anything needing a second argument is a
	form, not an action, and belongs on a screen that can ask for it."""
	admin = sources.text(ROOT / "apps/oneapp_control/oneapp_control/api/admin.py")
	tree = ast.parse(admin)
	for rows in declared.values():
		for row in rows:
			if not row.get("method"):
				continue
			name = row["method"].rsplit(".", 1)[1]
			fn = next(
				n for n in ast.walk(tree)
				if isinstance(n, ast.FunctionDef) and n.name == name
			)
			# Arguments with no default: the ones a caller has to supply.
			required = len(fn.args.args) - len(fn.args.defaults)
			assert required == 1, f"{name} needs more than the record to run"


def test_every_declared_screen_is_one_the_space_has(declared):
	"""A screen action naming a screen that does not exist is a button that
	navigates somewhere blank."""
	names = operator_screen_names()
	for key, rows in declared.items():
		for row in rows:
			if row.get("screen"):
				assert row["screen"] in names, f"{key}: {row['screen']} is not a screen"


def test_the_screen_an_action_is_declared_on_exists(declared):
	names = operator_screen_names()
	for key in declared:
		space, _, screen = key.partition("/")
		assert space == "onespace-ops", key
		assert screen in names, f"{key} is declared on a screen that does not exist"


def test_anything_that_cannot_be_undone_says_so_first(declared):
	"""Which actions those are is the declaration's call. Adopting a plan's
	current terms replaces quotas captured when the subscription was sold, and
	nothing here puts them back."""
	rows = {row["key"]: row for group in declared.values() for row in group}
	assert rows["adopt-terms"].get("confirm"), "grandfathering is dropped without a word"

	# The lifecycle's own. `purge` is the only action in the product that
	# destroys customer data, and `restore` replaces a site's database — a
	# dialog is the last thing between an operator and either.
	for key in ("purge", "restore", "run-lifecycle", "release"):
		assert rows[key].get("confirm"), f"{key} does something it cannot take back"


def test_the_purge_confirmation_says_the_word(declared):
	"""A confirmation that reads like every other confirmation is a button
	somebody clicks through. This one has to name what goes and that it is
	permanent, because after it there is nothing to appeal to."""
	rows = {row["key"]: row for group in declared.values() for row in group}
	text = rows["purge"]["confirm"].lower()

	assert "permanently" in text or "cannot be undone" in text, text
	assert "backup" in text or "cold copy" in text, text


# --------------------------------------------------------------------------- #
# Upload, which is a modifier and not a third kind of action
#
# The runner passes a method exactly one argument — the record's name — and
# that is the whole reason the Upload door had an endpoint and no button for
# as long as it did. `upload` is the one exception, narrow on purpose: one
# named argument rather than a mapping, because "the action is one this screen
# declares" stops meaning much once the caller also chooses what it is called
# with.
# --------------------------------------------------------------------------- #

def test_an_upload_action_says_so(spaceview, stub_frappe):
	declare(stub_frappe, {"s/screen": [
		{"key": "up", "label": "Upload", "method": "x.y", "upload": True},
	]})
	assert spaceview.actions("s", "screen")[0]["upload"] is True


def test_navigation_cannot_carry_a_file(spaceview, stub_frappe):
	"""A picker in front of a route change is a picker that goes nowhere."""
	declare(stub_frappe, {"s/screen": [
		{"key": "go", "label": "Go", "screen": "other", "upload": True},
	]})
	assert "upload" not in spaceview.actions("s", "screen")[0]


def test_an_ordinary_action_is_unchanged(spaceview, stub_frappe):
	declare(stub_frappe, {"s/screen": [{"key": "go", "label": "Go", "method": "x.y"}]})
	assert "upload" not in spaceview.actions("s", "screen")[0]


def _upload_ready(stub_frappe, stub_spaceview, seen: list):
	import sys
	import types

	module = types.ModuleType("fake_upload")
	module.run = lambda name, file_url="": seen.append((name, file_url)) or {"ok": True}
	sys.modules["fake_upload"] = module

	declare(stub_frappe, {"s/screen": [
		{"key": "up", "label": "Upload a delivery", "scope": "selection",
		 "method": "fake_upload.run", "upload": True},
	]})
	stub_spaceview("_resolve", lambda *a, **k: {"screen": "screen", "doctype": "Thing"})


def test_the_file_reaches_the_method(spaceview, stub_frappe, stub_spaceview):
	seen = []
	_upload_ready(stub_frappe, stub_spaceview, seen)
	stub_frappe.db.exists = lambda *a, **k: "FILE-1"
	stub_frappe.db.get_value = lambda *a, **k: "FILE-1"

	spaceview.run_action("s", "screen", "up", "T-1", file_url="/private/files/a.xml")
	assert seen == [("T-1", "/private/files/a.xml")]


def test_an_upload_action_with_no_file_says_what_is_missing(
	spaceview, stub_frappe, stub_spaceview
):
	seen = []
	_upload_ready(stub_frappe, stub_spaceview, seen)

	with pytest.raises(Exception, match="needs a file"):
		spaceview.run_action("s", "screen", "up", "T-1")
	assert not seen


def test_a_file_url_that_names_nothing_is_refused(spaceview, stub_frappe, stub_spaceview):
	seen = []
	_upload_ready(stub_frappe, stub_spaceview, seen)
	stub_frappe.db.exists = lambda *a, **k: None

	with pytest.raises(Exception, match="not here any more"):
		spaceview.run_action("s", "screen", "up", "T-1", file_url="/private/files/x")
	assert not seen


def test_somebody_elses_file_is_refused(spaceview, stub_frappe, stub_spaceview):
	"""A url is guessable, so the `File` is checked as a document rather than
	as a string."""
	seen = []
	_upload_ready(stub_frappe, stub_spaceview, seen)
	stub_frappe.db.exists = lambda *a, **k: "FILE-1"
	stub_frappe.db.get_value = lambda *a, **k: "FILE-1"
	stub_frappe.has_permission = lambda doctype, *a, **k: doctype != "File"

	with pytest.raises(Exception, match="cannot read that file"):
		spaceview.run_action("s", "screen", "up", "T-1", file_url="/private/files/a")
	assert not seen


def test_an_action_that_did_not_declare_upload_is_never_given_one(
	spaceview, stub_frappe, stub_spaceview
):
	"""The narrow point of the whole thing: a `file_url` in the request body
	reaches nothing that did not ask for it."""
	seen = []
	import sys
	import types

	module = types.ModuleType("fake_plain")
	module.run = lambda name: seen.append(name) or {"ok": True}
	sys.modules["fake_plain"] = module

	declare(stub_frappe, {"s/screen": [
		{"key": "go", "label": "Go", "method": "fake_plain.run"},
	]})
	stub_spaceview("_resolve", lambda *a, **k: {"screen": "screen", "doctype": "Thing"})

	# The method takes one argument; if the runner passed the url through, this
	# would raise a TypeError rather than run.
	spaceview.run_action("s", "screen", "go", "T-1", file_url="/private/files/a")
	assert seen == ["T-1"]


def test_the_sources_screen_has_the_button(stub_frappe):
	"""The Upload door of README §5. Its endpoint existed from the beginning
	and nothing called it, which made the one kind of source a manager tries
	first the one kind that could not be used."""
	import sys
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import actions as mobility

	rows = mobility.actions()["onemobility/sources"]
	upload = next(row for row in rows if row["key"] == "upload")
	assert upload["method"] == "oneapp.onemobility.load_feed"
	assert upload["upload"] is True
	# One at a time: the same file delivered to a selection would write the
	# same bytes to every source in it. The button is in both places — that is
	# no longer what `scope` decides — and disabled in the selection bar until
	# exactly one row is ticked.
	assert upload["scope"] == "one"
