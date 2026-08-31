"""Every way a screen reaches the database goes through Frappe's own checks.

The screens are the only door onto a customer's data, and there are two things
between a request and a row: the space's manifest, which says which doctypes
this screen may touch at all, and Frappe's permission machinery, which says
which *rows* of them this person may see. The second one is where User
Permissions live, and it is the one that is easy to lose by accident — a
`get_all` where a `get_list` was meant, an `ignore_permissions=True` copied
from a line above it, a raw query.

So this reads `spaceview.py` rather than trusting it. It is a structural test
and it does not know what any endpoint means; what it knows is that a new one
cannot quietly reach data without a gate in front of it.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APPVIEW = ROOT / "apps/oneapp/oneapp/oneapp_core/spaceview.py"

# Ours. Rows in these belong to the workspace's own bookkeeping — a saved view,
# a hidden one — and are already scoped by `user` and `space_code` in the
# filters. Everything else is the customer's data.
OURS = "OneSpace "

# Framework rows that follow a document rather than standing on their own. A
# Comment belongs to the record it is on: Frappe's own comment API inserts one
# for anybody who may *read* that record rather than requiring DocPerms on
# Comment, and `comment()` checks exactly that before it writes one. Named one
# at a time, so the next doctype like it has to argue its case here.
FOLLOWS_A_DOCUMENT = {"Comment"}

# What establishes which space a request is in, and therefore which doctypes it
# may name. `_resolve` and `_space` throw for anything outside the manifest;
# `_attachable` and `_may_write` are the same gate for the two endpoints that
# start from a document rather than from a screen.
GATES = {"_resolve", "_space", "_attachable", "_may_write", "_layout_doc"}

# Calls that reach the database.
REACHES = {
	"get_list", "get_all", "get_doc", "new_doc", "delete_doc", "get_value",
	"set_value", "exists", "delete", "sql", "get_cached_value", "count",
}


@pytest.fixture(scope="module")
def tree():
	return ast.parse(APPVIEW.read_text())


def _whitelisted(tree):
	for node in tree.body:
		if not isinstance(node, ast.FunctionDef):
			continue
		for decorator in node.decorator_list:
			call = decorator.func if isinstance(decorator, ast.Call) else decorator
			if isinstance(call, ast.Attribute) and call.attr == "whitelist":
				yield node
				break


def _called(node) -> set[str]:
	names = set()
	for child in ast.walk(node):
		if not isinstance(child, ast.Call):
			continue
		if isinstance(child.func, ast.Name):
			names.add(child.func.id)
		elif isinstance(child.func, ast.Attribute):
			names.add(child.func.attr)
	return names


def _doctypes(node) -> set[str]:
	"""Every doctype named as a literal anywhere in a function."""
	found = set()
	for child in ast.walk(node):
		if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
			if child.func.attr not in REACHES:
				continue
			if child.args and isinstance(child.args[0], ast.Constant):
				if isinstance(child.args[0].value, str):
					found.add(child.args[0].value)
		if isinstance(child, ast.Dict):
			for key, value in zip(child.keys, child.values):
				if (
					isinstance(key, ast.Constant) and key.value == "doctype"
					and isinstance(value, ast.Constant) and isinstance(value.value, str)
				):
					found.add(value.value)
	return found


def _named_doctype(call):
	"""Which doctype a call is about, where it says so.

	Three shapes, all in use: the first positional argument
	(`get_all("File", …)`), a dict literal (`get_doc({"doctype": "Comment"})`),
	and the same dict one call further out — `frappe.get_doc({…}).insert(…)`
	puts the keyword on `insert` and the doctype on the receiver.
	"""
	if call.args and isinstance(call.args[0], ast.Constant):
		return call.args[0].value
	source = call.args[0] if call.args else None
	if source is None and isinstance(call.func, ast.Attribute):
		source = call.func.value
		if isinstance(source, ast.Call):
			source = source.args[0] if source.args else None
	if isinstance(source, ast.Dict):
		for key, value in zip(source.keys, source.values):
			if isinstance(key, ast.Constant) and key.value == "doctype":
				return getattr(value, "value", None)
	return None


def test_every_endpoint_establishes_which_space_it_is_in(tree):
	"""Or touches nothing but our own bookkeeping.

	A whitelisted method that reaches a customer doctype without going through
	the manifest first is a way to read a doctype the space never granted —
	which is the one thing the screens exist to prevent.
	"""
	ungated = []
	for node in _whitelisted(tree):
		if _called(node) & GATES:
			continue
		named = _doctypes(node)
		if named and all(one.startswith(OURS) for one in named):
			continue
		ungated.append(node.name)
	assert not ungated, (
		"these reach data without establishing which space they are in: "
		+ ", ".join(sorted(ungated))
	)


def test_permissions_are_only_ever_skipped_for_our_own_rows(tree):
	"""`ignore_permissions=True` is where User Permissions go to die.

	It is right for a saved view — the row is ours, and the filters already
	name the user — and never right for a customer's records, where Frappe's
	own check is the thing doing the narrowing.
	"""
	offenders = []
	for child in ast.walk(tree):
		if not isinstance(child, ast.Call):
			continue
		skips = any(
			kw.arg == "ignore_permissions"
			and isinstance(kw.value, ast.Constant)
			and kw.value.value is True
			for kw in child.keywords
		)
		if not skips:
			continue
		named = _named_doctype(child)
		# A method call on a document — `doc.save(ignore_permissions=True)` —
		# is only ever reached after `_may_write`, which is the gate above.
		#
		# `frappe` is not a document. `frappe.get_all(something, …)` is an
		# Attribute on a Name exactly like `doc.save(…)` is, so this exemption
		# used to wave through any framework call whose doctype was a variable
		# rather than a literal — which is the shape a child table's query
		# takes, and the shape anything reaching for a doctype it computed
		# takes. Named explicitly rather than by shape.
		if named is None and isinstance(child.func, ast.Attribute):
			receiver = child.func.value
			if isinstance(receiver, ast.Name) and receiver.id not in {"frappe"}:
				continue
		if isinstance(named, str) and (named.startswith(OURS) or named in FOLLOWS_A_DOCUMENT):
			continue
		offenders.append(f"line {child.lineno}: {named or 'unnamed'}")
	assert not offenders, (
		"permissions skipped for something that is not ours: " + ", ".join(offenders)
	)


def test_nothing_reaches_the_database_by_hand(tree):
	"""`frappe.db.sql` runs past every check there is — the doctype's
	permissions, the field's permlevel, and User Permissions with them."""
	raw = [
		child.lineno
		for child in ast.walk(tree)
		if isinstance(child, ast.Call)
		and isinstance(child.func, ast.Attribute)
		and child.func.attr in {"sql", "sql_list", "multisql"}
	]
	assert not raw, f"raw SQL at lines {raw}"


def test_the_gates_are_still_called_that(tree):
	"""This test names four functions. If one is renamed and this is not, the
	rule above passes by knowing nothing."""
	defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
	assert GATES <= defined, f"missing: {sorted(GATES - defined)}"
