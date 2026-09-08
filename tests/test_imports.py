"""Every import in our own code points at something that exists.

A module split moves packages, and the imports at the top of a file are checked
the moment anything loads it — a stale one is an `ImportError` at boot and
nobody ships it. The dangerous ones are **deferred**: an import inside a
function body, written to break a cycle or to keep a heavy module out of the
boot path, resolves only when that function is called.

`shared/versions.py` had three of them, reaching for `oneapp.shared.sheets`
after `sheets` had become `onesheet` a level up. The whole Python suite passed.
The browser suite caught it as thirty-two failures and one line in a screenshot
— "Couldn't save: ModuleNotFoundError" — which is an expensive way to learn
that a dotted path is wrong.

So this reads every import statement in both apps, wherever it sits in the
file, and checks the module it names is on disk. It is `ast`, not an import: a
test that actually imported everything would need a site, and would be the
slowest thing in the suite.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APPS = ("oneapp", "oneapp_control")


def _sources():
	for app in APPS:
		base = ROOT / "apps" / app / app
		for path in sorted(base.rglob("*.py")):
			if "__pycache__" in path.parts:
				continue
			yield app, base, path


def _resolve(app: str, base: Path, path: Path, node) -> str | None:
	"""The dotted module an ImportFrom names, or None if it is not ours.

	`level` is the number of leading dots, counted from the *package* the file
	sits in — which for `a/b/c.py` is `a.b`, and for `a/b/__init__.py` is
	`a.b` as well.
	"""
	here = path.parent if path.name == "__init__.py" else path.parent
	if node.level:
		up = here
		for _ in range(node.level - 1):
			up = up.parent
		try:
			prefix = up.relative_to(base.parent).as_posix().replace("/", ".")
		except ValueError:
			return None
		return f"{prefix}.{node.module}" if node.module else prefix
	if node.module and node.module.split(".")[0] in APPS:
		return node.module
	return None


def _exists(dotted: str) -> bool:
	"""Whether `a.b.c` is a package or a module under `apps/`."""
	parts = dotted.split(".")
	base = ROOT / "apps" / parts[0]
	target = base.joinpath(*parts)
	return (target / "__init__.py").exists() or target.with_suffix(".py").exists()


def test_every_import_of_ours_points_at_something():
	missing = []
	for app, base, path in _sources():
		tree = ast.parse(path.read_text(), filename=str(path))
		for node in ast.walk(tree):
			if isinstance(node, ast.ImportFrom):
				dotted = _resolve(app, base, path, node)
			elif isinstance(node, ast.Import):
				dotted = next(
					(a.name for a in node.names if a.name.split(".")[0] in APPS), None
				)
			else:
				continue
			if not dotted or _exists(dotted):
				continue
			# `from x import y` where y is a name rather than a submodule is
			# fine as long as x resolves; only the module half is checked.
			missing.append(
				f"{path.relative_to(ROOT)}:{node.lineno}: {dotted} does not exist"
			)

	assert not missing, (
		"these imports name a module that is not on disk — a deferred one fails "
		"only when its function is called:\n  " + "\n  ".join(missing)
	)


@pytest.mark.parametrize("app", APPS)
def test_the_sweep_reached_the_whole_app(app):
	"""A guard that walks nothing passes silently."""
	found = [p for a, _, p in _sources() if a == app]
	assert len(found) > 20, f"{app}: only {len(found)} python files swept"
