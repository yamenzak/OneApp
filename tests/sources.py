"""Reading a module's source when it may have become a package.

Several guards here work by parsing source rather than by trusting it, and each
had a path like `api/admin.py` written into it. Those modules are packages now —
`admin`, `importer`, `mailbox`, `spaceview` — and a guard that opens the old
path does not fail loudly, it fails at collection, which is worse: the rule it
was keeping simply stops being checked.

So one place knows how to find a module, and knows that `foo.py` and `foo/` are
the same answer to the same question.
"""

from pathlib import Path


def files(path: Path) -> list[Path]:
	"""Every source file of a module, `__init__` excluded.

	`__init__` is re-exports, so a guard counting endpoints or database calls
	would otherwise see each one twice.
	"""
	if path.is_dir():
		return sorted(p for p in path.glob("*.py") if p.name != "__init__.py")
	if path.exists():
		return [path]
	package = path.with_suffix("")
	assert package.is_dir(), f"no module or package at {path}"
	return files(package)


def text(path: Path) -> str:
	"""All of it as one string, for the guards that only grep."""
	return "\n".join(p.read_text() for p in files(path))
