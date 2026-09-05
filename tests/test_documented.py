"""Every endpoint says what it is for.

A whitelisted method is this product's public API: the SPA calls it by name,
and so could anything else holding a session. Thirty of them said nothing at
all — not because anybody decided they were obvious, but because a docstring is
the easiest thing to leave for later and nothing ever asked for it.

Scoped to whitelisted functions on purpose. A private helper earns its
explanation by being hard to follow; an endpoint earns it by being reachable.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Generated controllers. `gen_doctypes.py` writes them and they are a class
# statement and nothing else, so a docstring here would be a docstring on
# boilerplate — and one the generator would overwrite.
GENERATED = "/doctype/"


def endpoints() -> list[tuple[str, str, ast.FunctionDef]]:
	found = []
	for path in sorted((ROOT / "apps").rglob("*.py")):
		if "node_modules" in str(path) or GENERATED in str(path):
			continue
		try:
			tree = ast.parse(path.read_text())
		except SyntaxError:
			continue
		for node in tree.body:
			if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
				continue
			if any("whitelist" in ast.unparse(d) for d in node.decorator_list):
				found.append((str(path.relative_to(ROOT)), node.name, node))
	return found


def test_the_reader_found_the_endpoints():
	assert len(endpoints()) > 150, f"only found {len(endpoints())} whitelisted methods"


@pytest.mark.parametrize(
	"where,name,node", endpoints(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_every_endpoint_has_a_docstring(where, name, node):
	doc = ast.get_docstring(node)
	assert doc, (
		f"{where}: `{name}` is whitelisted, so it is reachable by anything "
		f"holding a session, and it says nothing about what it does."
	)
	assert len(doc.split()) >= 4, (
		f"{where}: `{name}`'s docstring is {doc!r}, which restates the name"
	)
