"""The screen package is layered, and this is what keeps it that way.

`spaceview` was one 4,000-line module. Splitting it was only worth doing if it
stays split, and the way a package like this collapses is not by being merged —
it is by one module importing from a module below it, then another, until every
file needs every other and the directory is a single module wearing nineteen
filenames.

So: the order in `LAYERS` is the import order. A module may use the ones above
it and never the ones below. Adding a module means adding it here, which is the
moment to ask where it really sits.
"""

import ast

import pytest

import spaceview_source

# Read from the package's own docstring rather than restated here, so the map a
# reader is given and the rule the tests enforce cannot drift apart.
def declared_layers() -> list[str]:
	doc = ast.get_docstring(ast.parse((spaceview_source.PACKAGE / "__init__.py").read_text()))
	block = doc.split("## The layers", 1)[1]
	names = []
	for line in block.splitlines():
		parts = line.split()
		if len(parts) >= 2 and line.startswith("    ") and not line.startswith("     "):
			if (spaceview_source.PACKAGE / f"{parts[0]}.py").exists():
				names.append(parts[0])
	return names


LAYERS = declared_layers()


def test_the_docstring_lists_every_module():
	"""A module missing from the map is a module nobody placed."""
	on_disk = {p.stem for p in spaceview_source.files()}
	assert set(LAYERS) == on_disk, (
		"the layer map in spaceview/__init__.py and the modules on disk "
		f"disagree: {sorted(on_disk ^ set(LAYERS))}"
	)


def imports_of(module: str) -> set[str]:
	"""Sibling modules this one imports from."""
	tree = ast.parse(spaceview_source.module(module))
	found = set()
	for node in ast.walk(tree):
		if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
			found.add(node.module)
		elif isinstance(node, ast.ImportFrom) and node.level == 1 and not node.module:
			found |= {a.name for a in node.names}
	return found


@pytest.mark.parametrize("module", LAYERS)
def test_a_module_only_imports_from_above_it(module):
	rank = LAYERS.index(module)
	for other in imports_of(module):
		assert other in LAYERS, f"{module} imports {other}, which is not a layer"
		assert LAYERS.index(other) < rank, (
			f"{module} imports {other}, which is below it. Either it belongs "
			f"higher up, or the thing it needs does — see the layer map in "
			f"spaceview/__init__.py."
		)


def test_no_layer_reaches_back_through_the_package():
	"""`from . import x` inside a layer is the cycle this rule exists to stop.

	It resolves at call time rather than import time, so Python allows it and
	the layering is gone without a single import error.
	"""
	for module in LAYERS:
		tree = ast.parse(spaceview_source.module(module))
		for node in ast.walk(tree):
			if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
				pytest.fail(
					f"{module} does `from . import ...`, which imports the "
					f"package and every layer with it"
				)
