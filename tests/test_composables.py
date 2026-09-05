"""A composable is called with state that already exists.

The bug this exists for: extracting `useCrumbs` out of `ScreenHost.vue` moved
the call to the top of the script and left `viewType` declared sixty lines
below it. JavaScript hoists the binding but not the value, so the call read a
`const` in its temporal dead zone — a `ReferenceError` on the first line of
`setup`, a blank page, and a browser suite where every locator in every spec
times out at once. Nothing else saw it: the SFC compiles, the bundle builds,
`no-undef` is satisfied because the name *is* declared, and eslint's
`no-use-before-define` cannot tell a reference that runs now from one inside a
handler that runs later, so turning it on flags seventy safe lines and trains
everyone to switch it off.

This is the narrow version of that rule, and the narrowness is the point: a
`use*(...)` call in the top level of `<script setup>` runs immediately, so every
bare name in its arguments has to be declared above it. A name inside an arrow
body does not — that runs when somebody calls it — which is exactly why the
hosts pass their loaders as thunks.
"""

import re
from pathlib import Path

import pytest
from vendored import is_vendored

ROOT = Path(__file__).resolve().parent.parent
SPAS = sorted(ROOT.glob("apps/*/frontend/src"))


def scripts() -> list[tuple[Path, str]]:
	"""Every `<script setup>` block that calls a composable."""
	found = []
	for src in SPAS:
		for path in sorted(src.rglob("*.vue")):
			if is_vendored(path):
				continue
			body = path.read_text()
			if "<script setup>" not in body:
				continue
			block = body.split("<script setup>", 1)[1].rsplit("</script>", 1)[0]
			if re.search(r"^const \{[^}]*\} = use[A-Z]\w*\(", block, re.M):
				found.append((path, block))
	return found


def test_the_reader_found_the_composable_calls():
	assert scripts(), "no component destructures a composable — has the pattern moved?"


def declared_above(block: str, upto: int) -> set[str]:
	"""Names a top-level `const`/`let`/`function` binds before this line."""
	names = set()
	for line in block.splitlines()[:upto]:
		for m in re.finditer(r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)", line):
			names.add(m.group(1))
		# Destructured: `const { a, b: c } = ...`
		m = re.match(r"^(?:const|let)\s*\{([^}]*)\}", line)
		if m:
			for part in m.group(1).split(","):
				names.add(part.split(":")[-1].strip())
		m = re.match(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", line)
		if m:
			names.add(m.group(1))
	return {n for n in names if n}


@pytest.mark.parametrize("path,block", scripts(), ids=lambda v: getattr(v, "name", ""))
def test_a_composable_only_reads_state_declared_above_it(path, block):
	lines = block.splitlines()
	for n, line in enumerate(lines):
		if not re.match(r"^const \{[^}]*\} = use[A-Z]\w*\(", line):
			continue
		# The argument list, by bracket depth from the call's own paren. A
		# terminator matched by eye — "a line that is just `})`" — runs straight
		# past a call ending in `])` and reads whatever follows as an argument.
		depth, end = 0, n
		started = False
		while end < len(lines):
			for ch in lines[end]:
				if ch in "([{":
					depth += 1
					started = True
				elif ch in ")]}":
					depth -= 1
			if started and depth <= 0:
				break
			end += 1
		# From after the `= useX(`, so the names being *bound* on the left are
		# not read as names being *passed* on the right.
		args = "\n".join(lines[n:end + 1]).split("= use", 1)[1]
		# Arrow bodies run later, so what they read is not this call's problem.
		args = re.sub(r"\([^)]*\)\s*=>.*|\w+\s*=>.*", "", args)
		# And a quoted string is a value, not a name: a column keyed `'remove'`
		# is not a reference to the `remove` defined further down.
		args = re.sub(r"'[^']*'|\"[^\"]*\"|`[^`]*`", "", args)
		known = declared_above(block, n)
		for name in set(re.findall(r"\b([a-z][\w$]*)\b(?!\s*:)", args)):
			if name in ("const", "use") or name.startswith("use"):
				continue
			# Only names this file binds at the top level are ours to order.
			if name in declared_above(block, len(lines)) and name not in known:
				pytest.fail(
					f"{path.name}: {lines[n].strip()} reads `{name}`, which is "
					f"declared below it. The call runs at setup, so this is a "
					f"ReferenceError and a blank page — move the call down, or "
					f"pass a thunk the way the loaders are passed."
				)
