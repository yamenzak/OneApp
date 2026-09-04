"""Where the screen layer's source lives, for the tests that read it.

`spaceview` was one 4,000-line module and is a package now. Several guards here
work by parsing that source rather than by trusting it — which endpoint checks
which gate, what reaches the database by hand — and every one of them had the
old path written into it. One place knows the path now, so the next split moves
one line instead of seven.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "apps/oneapp/oneapp/oneapp_core/spaceview"


def files() -> list[Path]:
	"""Every module in the package, `__init__` excluded.

	`__init__` is re-exports and nothing else, so a guard counting endpoints or
	database calls would see each one twice.
	"""
	return sorted(p for p in PACKAGE.glob("*.py") if p.name != "__init__.py")


def source() -> str:
	"""All of it as one string, for the checks that only grep."""
	return "\n".join(p.read_text() for p in files())


def trees() -> list[ast.Module]:
	"""One parsed tree per module, for the checks that walk statements."""
	return [ast.parse(p.read_text()) for p in files()]


def tree() -> ast.Module:
	"""Every module's statements under one Module node.

	The guards that walk this care about top-level functions and what they call,
	and none of them cares which file a function came from.
	"""
	merged = ast.Module(body=[], type_ignores=[])
	for one in trees():
		merged.body.extend(one.body)
	return merged


def module(name: str) -> str:
	"""One module's source, for a check that means one layer.

	`source()` concatenates in filename order, so a check written as "the first
	`can_create` in the file" silently starts reading a different function the
	day a module is added. Name the layer instead.
	"""
	path = PACKAGE / f"{name}.py"
	assert path.exists(), f"no {name} module in the screen package"
	return path.read_text()
