"""Where a file in the SPA is, by name, when the directory it sits in may change.

Several guards read a `.vue` or a `.js` to check what it does, and each had a
path like `components/screen/RecordView.vue` written into it. That path was true
until the screen components were grouped into families — and then twelve guards
failed at once, none of them because the rule they keep had been broken. The
same happened again when `lib/` was grouped.

A guard that cannot find its file is worse than one that fails: it stops
checking. So one place knows how to find a file, and a move is a move rather
than a day of path edits.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPA = ROOT / "apps/oneapp/frontend/src"
COMPONENTS = SPA / "components"


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
	return _one(ROOT / f"apps/{app}/frontend/src/lib", name)


def module_source(name: str, app: str = "oneapp") -> str:
	return module(name, app).read_text()


def imports(source: str, name: str) -> bool:
	"""Whether this source pulls in `lib/<family>/<name>`, family unnamed."""
	return re.search(rf"from '@/lib/[a-z]+/{re.escape(name)}'", source) is not None


def screen() -> list[Path]:
	"""Every component that draws part of a screen, in any of its families."""
	return sorted((COMPONENTS / "screen").rglob("*.vue"))
