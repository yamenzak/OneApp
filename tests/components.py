"""Finding a component by name, when the directory it sits in may change.

Several guards here read a `.vue` file to check what it draws, and each had a
path like `components/screen/RecordView.vue` written into it. That path was true
until the screen components were grouped into families — and then twelve guards
failed at once, none of them because the rule they keep had been broken.

A guard that cannot find its file is worse than one that fails: it stops
checking. So one place knows how to find a component, and a move is a move
rather than a day of path edits.
"""

from pathlib import Path

SPA = Path(__file__).resolve().parent.parent / "apps/oneapp/frontend/src"
COMPONENTS = SPA / "components"


def path(name: str) -> Path:
	"""Where `Foo.vue` lives, wherever it has been grouped."""
	if not name.endswith(".vue"):
		name += ".vue"
	found = sorted(COMPONENTS.rglob(name))
	assert found, f"no component named {name} under {COMPONENTS}"
	assert len(found) == 1, f"{name} exists {len(found)} times: {found}"
	return found[0]


def source(name: str) -> str:
	return path(name).read_text()


def screen() -> list[Path]:
	"""Every component that draws part of a screen, in any of its families."""
	return sorted((COMPONENTS / "screen").rglob("*.vue"))
