"""Where a file in the SPA is, by name, when the directory it sits in may change.

Several guards read a `.vue` or a `.js` to check what it does, and each had a
path like `components/screen/RecordView.vue` written into it. That path was true
until the screen components were grouped into families — and then twelve guards
failed at once, none of them because the rule they keep had been broken. The
same happened again when `lib/` was grouped.

A guard that cannot find its file is worse than one that fails: it stops
checking. So one place knows how to find a file, and a move is a move rather
than a day of path edits. It earned itself a third time when the SPA was split
into modules: the search root is now the whole of `src`, because a component
lives in the module it belongs to and a library lives in `shared/lib` or in one
module's own — and which is which is not a guard's business.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from spa.spec import where as _laid_out  # noqa: E402
SPA = ROOT / "apps/oneapp/frontend/src"
COMPONENTS = SPA


def _one(where: Path, name: str) -> Path:
	found = sorted(where.rglob(name))
	assert found, f"nothing named {name} under {where}"
	assert len(found) == 1, f"{name} exists {len(found)} times: {found}"
	return found[0]


def path(name: str) -> Path:
	"""Where `Foo.vue` lives, wherever it has been grouped."""
	if not name.endswith(".vue"):
		name += ".vue"
	return _one(COMPONENTS, name)


def source(name: str) -> str:
	return path(name).read_text()


def module(name: str, app: str = "oneapp") -> Path:
	"""Where `lib/foo.js` lives, whichever family it was grouped into."""
	if not name.endswith(".js"):
		name += ".js"
	return _one(ROOT / f"apps/{app}/frontend/src", name)


def module_source(name: str, app: str = "oneapp") -> str:
	return module(name, app).read_text()


def imports(source: str, name: str) -> bool:
	"""Whether this source pulls in `<somewhere>/<name>`, the somewhere unnamed."""
	return re.search(rf"from '@/[\w/]+/{re.escape(name)}'", source) is not None


def screen() -> list[Path]:
	"""Every component that draws part of a screen, in any of its families."""
	return sorted(p for d in dirs("screen") for p in d.rglob("*.vue"))


# --------------------------------------------------------------------------- #
# Where a bundle keeps a generated file
# --------------------------------------------------------------------------- #
#
# The finders above search by name, which is what a guard reading one component
# wants. These answer the other question: a guard that knows the *generated*
# path — `src/lib/runtime/boot.js` — and has to open it in a bundle that may
# have moved it. One table decides that, in `scripts/spa/spec.py`, and it is the
# same table the generator writes by, so the two cannot disagree.


def spa(app: str, path: str) -> Path:
	"""A generated file on disk, wherever this bundle keeps it."""
	return ROOT / "apps" / app / "frontend" / _laid_out(app, path)


def generated(app: str, path: str) -> str:
	"""The same file, as a key of what `gen_frontend.render()` returns."""
	return f"frontend/{_laid_out(app, path)}"


def dirs(name: str, app: str = "oneapp") -> list[Path]:
	"""Every directory called `name` in this bundle.

	`pages` is one directory in a flat bundle and one per module in a split
	one, and a guard over "every page" means the same thing either way.
	"""
	root = ROOT / f"apps/{app}/frontend/src"
	return sorted(p for p in root.rglob(name) if p.is_dir())


def within(name: str, app: str = "oneapp", pattern: str = "*.vue") -> list[Path]:
	"""Everything matching `pattern` directly inside any `name` directory."""
	return sorted(f for d in dirs(name, app) for f in d.glob(pattern))
