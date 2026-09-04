"""The two generators are packages now, and this keeps them flat.

`gen_doctypes.py` was 2,944 lines and `gen_frontend.py` 3,214 — both a wall of
content with a hundred lines of assembly at the bottom. The content moved into
`scripts/doctypes/` and `scripts/spa/`, one module per subject.

The shape that makes them worth splitting is flat: every module reads the shared
vocabulary out of `spec` and nothing else. A module importing from a sibling is
how that becomes a graph, and a graph is how "where does this go?" stops having
an answer. So: `spec` is the only sibling anyone may import.

The docstring in each `__init__` is the map, and it is read back here rather
than restated, so what a reader is told and what the suite enforces cannot
drift apart.
"""

import ast
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
PACKAGES = ["doctypes", "spa"]


def modules(package: str) -> list[Path]:
	return sorted(p for p in (SCRIPTS / package).glob("*.py") if p.name != "__init__.py")


def declared(package: str) -> set[str]:
	"""The module names listed in the package's own docstring."""
	doc = ast.get_docstring(ast.parse((SCRIPTS / package / "__init__.py").read_text()))
	names = set()
	for line in doc.splitlines():
		parts = line.split()
		if line.startswith("  ") and not line.startswith("   ") and len(parts) >= 2:
			names.add(parts[0])
	return names


@pytest.mark.parametrize("package", PACKAGES)
def test_the_docstring_lists_every_module(package):
	"""A module missing from the map is a module nobody placed."""
	on_disk = {p.stem for p in modules(package)}
	assert declared(package) == on_disk, (
		f"the map in scripts/{package}/__init__.py and the modules on disk "
		f"disagree: {sorted(on_disk ^ declared(package))}"
	)


@pytest.mark.parametrize("package", PACKAGES)
def test_spec_is_the_only_sibling_anyone_imports(package):
	for path in modules(package):
		siblings = set()
		for node in ast.walk(ast.parse(path.read_text())):
			if isinstance(node, ast.ImportFrom) and node.level == 1:
				siblings.add(node.module or "")
				if not node.module:
					siblings |= {a.name for a in node.names}
		assert siblings <= {"spec"}, (
			f"scripts/{package}/{path.name} imports from {sorted(siblings - {'spec'})}. "
			"Shared vocabulary belongs in spec; a sibling import is the first "
			"edge of the graph this split exists to avoid."
		)


def test_spec_imports_nothing_of_its_own():
	"""The top of each package has to actually be the top."""
	for package in PACKAGES:
		tree = ast.parse((SCRIPTS / package / "spec.py").read_text())
		relative = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level]
		assert not relative, f"scripts/{package}/spec.py imports from its own package"


def test_the_generators_hold_only_the_assembly():
	"""Content that creeps back into the entry point is the split undone."""
	for name, limit in (("gen_doctypes.py", 400), ("gen_frontend.py", 200)):
		lines = len((SCRIPTS / name).read_text().splitlines())
		assert lines <= limit, (
			f"scripts/{name} is {lines} lines. It is the assembly — which file "
			f"gets which content — and the content belongs in a module beside it."
		)
