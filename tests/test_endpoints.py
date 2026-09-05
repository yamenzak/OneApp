"""Two ways a whitelisted endpoint is silently not there.

Both were found in the Drive and both were invisible from the layer above:
nothing failed, nothing logged, and the feature was simply absent.

The first is a name. A package re-exports what its modules whitelist, and the
client calls `oneapp.oneapp_core.drive.details` — the *package* path. A function
the package does not re-export is a method Frappe cannot resolve, so the call
404s and the caller's `.catch` swallows it.

The second is a transaction. Frappe commits a request only when its HTTP method
is one that changes server state (`frappe/app.py`), so a write inside a `GET` is
rolled back at the end of it. The route answers 200 and the row is unchanged.
`frappe.local.flags.commit` is the framework's own way for a read to say that
this one writes, and a read that writes without it is a read that does not.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "apps/oneapp/oneapp"

# What counts as writing. Deliberately blunt: a false positive costs one
# `flags.commit` on something that did not need it, and a false negative costs
# a feature nobody can see is missing.
WRITES = re.compile(
	r"\bdb_set\(|frappe\.db\.set_value\(|\.insert\(|\.save\(|"
	r"frappe\.delete_doc\(|frappe\.db\.delete\("
)


def _whitelisted(path: Path):
	"""`(name, methods, source)` for every whitelisted function in a module."""
	source = path.read_text()
	found = []
	for node in ast.parse(source).body:
		if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
			continue
		for decorator in node.decorator_list:
			call = decorator if isinstance(decorator, ast.Call) else None
			target = call.func if call else decorator
			if not (isinstance(target, ast.Attribute) and target.attr == "whitelist"):
				continue
			methods = []
			if call:
				for keyword in call.keywords:
					if keyword.arg == "methods":
						methods = [entry.value for entry in keyword.value.elts]
			found.append((node.name, methods, ast.get_source_segment(source, node) or ""))
	return found


def test_a_package_re_exports_everything_it_whitelists():
	"""`drive.details` was whitelisted, never re-exported, and therefore a 404
	for three stages — which is why Recents was empty on every site."""
	missing = []
	for init in sorted(APP.rglob("__init__.py")):
		exported = init.read_text()
		if "import" not in exported:
			continue
		for module in sorted(init.parent.glob("*.py")):
			if module.name == "__init__.py":
				continue
			for name, _methods, _source in _whitelisted(module):
				if not re.search(rf"\b{name}\b", exported):
					missing.append(f"{module.relative_to(APP)}:{name}")

	assert not missing, (
		"whitelisted but not re-exported by its package, so the client's call "
		"resolves to no such method: " + ", ".join(missing)
	)


def test_a_read_that_writes_says_so():
	"""Otherwise the write is rolled back at the end of the request it was made
	in, and the route still answers 200."""
	silent = []
	for module in sorted(APP.rglob("*.py")):
		for name, methods, source in _whitelisted(module):
			if methods and "GET" not in methods:
				continue
			if not WRITES.search(source):
				continue
			if "flags.commit" in source or "db.commit()" in source:
				continue
			silent.append(f"{module.relative_to(APP)}:{name}")

	assert not silent, (
		"a GET-able endpoint that writes without `frappe.local.flags.commit`, "
		"so the write is discarded: " + ", ".join(silent)
	)
