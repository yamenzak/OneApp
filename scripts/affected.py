#!/usr/bin/env python3
"""Which browser specs a change can actually break.

`yarn e2e` is 263 specs across two viewports and half an hour, and it was being
run for changes that touched three files — because the alternative was picking
specs by memory, and memory is exactly what fails here. Moving the settings gear
out of the account menu broke `drive.spec.js` and the phone's More sheet, and
neither of those is a settings file. A run chosen by hand would have missed both.

So the choice is made mechanically, from three facts that are already in the
tree:

  * **Some files are shared.** `App.vue`, the shell, the generators, the seeder:
    a change there can reach any spec, so it means everything. Nothing clever —
    a list, in `SHARED`.
  * **A component is reached through its importers.** A change to one panel is
    a change to whatever imports it, up to a page. That closure is read from the
    `import` statements rather than guessed.
  * **A spec names what it drives.** `data-slot="mail-away"`, a route, an
    endpoint's dotted path. So the specs that mention anything the closure
    *provides* are the ones that can see the change.

Anything it cannot attribute is `all`, deliberately. The failure that matters is
a spec that should have run and did not, and this is the direction that fails
towards a slow run rather than a broken push.

    scripts/affected.py                 # against the working tree
    scripts/affected.py HEAD~3          # against a commit
    scripts/dev.sh e2e                  # runs exactly what this prints

Prints one spec path per line, or the single word `all`.
"""

from __future__ import annotations

import fnmatch
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPA = ROOT / "apps/oneapp/frontend"
SRC = SPA / "src"
E2E = SPA / "e2e"

#: A change here can reach any spec, so it means all of them.
#:
#: Every one of these is either mounted by every route (the shell), read by
#: every spec (the auth helper, the config), or the source of a file that is
#: (a generator, the fixture). This list is the whole of the judgement in this
#: script, which is why it is a list and not a heuristic.
SHARED = (
	"apps/oneapp/frontend/src/App.vue",
	"apps/oneapp/frontend/src/main.js",
	"apps/oneapp/frontend/src/router*",
	"apps/oneapp/frontend/src/modules/onespace/components/AppShell.vue",
	# The rail, which is three components under `shell/` since the launcher
	# and the foot were split out of it, plus the sidebar it sits in.
	"apps/oneapp/frontend/src/modules/onespace/components/shell/*",
	"apps/oneapp/frontend/src/modules/onespace/components/SpaceSidebar.vue",
	"apps/oneapp/frontend/src/modules/onespace/lib/shell/*",
	"apps/oneapp/frontend/src/shared/lib/runtime/*",
	"apps/oneapp/frontend/src/ui.js",
	"apps/oneapp/frontend/e2e/auth.js",
	"apps/oneapp/frontend/playwright.config.js",
	"apps/oneapp/frontend/vite.config.js",
	"apps/oneapp/frontend/tailwind.config.js",
	"apps/oneapp/oneapp/hooks.py",
	# Every screen in every space is resolved and read through these two, so a
	# change in either is a change to every list, record and view there is.
	"apps/oneapp/oneapp/onespace/spaceview/resolve.py",
	"apps/oneapp/oneapp/onespace/spaceview/records.py",
	"scripts/gen_frontend.py",
	"scripts/spa/*",
	"scripts/doctypes/*",
	"scripts/seed_dev_space.py",
	"scripts/dev.sh",
)

#: Changed and nothing in a browser can tell. Documentation, the Python guards,
#: the operator console's own SPA — none of them is what these specs drive.
IGNORED = (
	"docs/*",
	"*.md",
	"tests/*",
	"apps/oneadmin/*",
	".github/*",
	"*.test.js",
)


def changed(against: str | None) -> list[str]:
	"""Paths this change touches, as the repository sees them.

	The working tree by default — staged, unstaged and untracked — because the
	question is usually "what am I about to push", asked before the commit
	exists.
	"""
	if against:
		out = _git("diff", "--name-only", against)
	else:
		out = _git("diff", "--name-only", "HEAD") + _git(
			"ls-files", "--others", "--exclude-standard")
	return sorted(set(out))


def _git(*args: str) -> list[str]:
	done = subprocess.run(
		["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
	return [line for line in done.stdout.splitlines() if line.strip()]


def _matches(path: str, patterns) -> bool:
	return any(fnmatch.fnmatch(path, one) for one in patterns)


# --------------------------------------------------------------------------- #
# The import graph
# --------------------------------------------------------------------------- #

IMPORT = re.compile(r"""(?:from|import)\s+['"]([^'"]+)['"]""")


def _resolve(spec: str, source: pathlib.Path) -> pathlib.Path | None:
	"""One import specifier as a file, or nothing if it leaves the SPA.

	`@/` is the alias the whole SPA uses for `src/`; a relative path is relative
	to the importer. A bare name is a package, and a package is not a file this
	is tracking.
	"""
	if spec.startswith("@/"):
		base = SRC / spec[2:]
	elif spec.startswith("."):
		base = (source.parent / spec).resolve()
	else:
		return None

	if base.is_file():
		return base
	# `./thing` is `thing.js`, `thing.vue`, or a directory with an index in it —
	# all three appear in this tree. Built as a path rather than with
	# `with_name`, which refuses a name containing a separator.
	for suffix in (".js", ".vue", ".ts", "/index.js", "/index.vue"):
		if (found := pathlib.Path(str(base) + suffix)).is_file():
			return found
	return None


# What a `lib/` module exports, as its callers write it. The barrel above is a
# namespace — `workspace.mailAway` — so the name is how a component reaches one
# endpoint through it, and the only link that survives the re-export.
MEMBER = re.compile(
	r"""^\s*(\w+):\s*(?:\(|async|function)|^export\s+(?:async\s+)?function\s+(\w+)"""
	r"""|^export\s+const\s+(\w+)""",
	re.M,
)


def members_of(path: pathlib.Path) -> set[str]:
	"""The names a `lib/` module hands out, ignoring the very short ones.

	Two letters matches half the tree and tells you nothing; a name like
	`mailAway` matches the one component that calls it.
	"""
	found = {name for group in MEMBER.findall(path.read_text(errors="ignore"))
	         for name in group if name}
	return {one for one in found if len(one) > 4}


def callers(namespace: str, members: set[str]) -> set[pathlib.Path]:
	"""Every file that calls one of those names *on that namespace*.

	The namespace matters. A bare `.profile` matches `data.profile` in half the
	tree and answers "everything"; `workspace.profile` matches the four
	components that actually call this module.
	"""
	if not members:
		return set()
	wanted = re.compile(rf"\b{namespace}\.(" + "|".join(sorted(members)) + r")\b")
	return {
		one for one in list(SRC.rglob("*.vue")) + list(SRC.rglob("*.js"))
		if wanted.search(one.read_text(errors="ignore"))
	}


def importers() -> dict[pathlib.Path, set[pathlib.Path]]:
	"""Who imports each file. The graph, read backwards."""
	back: dict[pathlib.Path, set[pathlib.Path]] = {}
	for path in list(SRC.rglob("*.vue")) + list(SRC.rglob("*.js")):
		for spec in IMPORT.findall(path.read_text(errors="ignore")):
			if target := _resolve(spec, path):
				back.setdefault(target, set()).add(path)
	return back


def _is_barrel(path: pathlib.Path) -> bool:
	"""A re-export with no behaviour of its own: `lib/workspace/index.js`.

	These are why the closure has to stop somewhere. Every component in the SPA
	imports `workspace` from one line in a barrel, so expanding a barrel's
	importers maps *any* endpoint change to *every* component — and 44 specs is
	not an answer, it is the question restated. A barrel is a namespace rather
	than a thing that behaves, so it is included and not expanded.
	"""
	return path.name in ("index.js", "index.vue") and path.parent != SRC


def reached(seeds: set[pathlib.Path]) -> set[pathlib.Path]:
	"""The seeds and everything that imports them, all the way up.

	A change to `SettingsAttach.vue` is a change to `SettingsFields.vue`, which
	is a change to `SettingsShell.vue`. Only the top of that chain is named by
	any spec, so without the closure a leaf component maps to nothing.
	"""
	back = importers()
	seen = set(seeds)
	queue = list(seeds)
	while queue:
		one = queue.pop()
		if _is_barrel(one) and one not in seeds:
			continue
		for who in back.get(one, ()):
			if who not in seen:
				seen.add(who)
				queue.append(who)
	return seen


# --------------------------------------------------------------------------- #
# What a file provides, and what a spec asks for
# --------------------------------------------------------------------------- #

# A spec finds things by slot, by route and by endpoint, so those are the three
# vocabularies worth indexing. Anything dynamic — a slot built by interpolation
# — is skipped rather than guessed at: `${one.key}-link` names nothing findable.
SLOT = re.compile(r"""data-slot=["'`]([\w-]+)["'`]""")
ROUTE = re.compile(r"""name:\s*['"]([A-Z]\w+)['"]""")
ENDPOINT = re.compile(r"""['"](oneapp\.[\w.]+)['"]""")
WHITELISTED = re.compile(r"""@frappe\.whitelist[^\n]*\ndef\s+(\w+)""")


def tokens_of(path: pathlib.Path) -> set[str]:
	"""The names a file puts into the world, for a spec to ask for."""
	return names_in(path, path.read_text(errors="ignore"))


def names_in(path: pathlib.Path, text: str) -> set[str]:
	"""The same, given the text — so a file that is gone can still answer."""
	found = set(SLOT.findall(text)) | set(ENDPOINT.findall(text))
	if path.suffix in (".js", ".vue"):
		found |= set(ROUTE.findall(text))
	return found


def at_head(path: str) -> str | None:
	"""What a file said before this change, or None if it never existed.

	A *deleted* file used to be the one thing this script could not attribute,
	so removing one component meant running all 263 specs — which is how
	deleting `FacetBar.vue` came to cost half an hour. It is no less
	attributable than a changed one: the slots and routes it provided are in
	git, and the specs that name any of them are exactly the ones at risk of
	having lost what they were driving.
	"""
	done = subprocess.run(
		["git", "show", f"HEAD:{path}"],
		cwd=ROOT, capture_output=True, text=True, check=False,
	)
	return done.stdout if done.returncode == 0 else None


def python_tokens(path: pathlib.Path) -> set[str]:
	"""A Python module's endpoints, as the SPA and the specs name them.

	`oneapp/onespace/me.py` provides `oneapp.onespace.me.save_profile`,
	which is the string `lib/workspace/settings.js` calls and the string
	`settings.spec.js` asserts against — so one token reaches both ends.
	"""
	try:
		module = path.relative_to(ROOT / "apps/oneapp")
	except ValueError:
		return set()

	dotted = str(module.with_suffix("")).replace("/", ".")
	text = path.read_text(errors="ignore")
	return {f"{dotted}.{name}" for name in WHITELISTED.findall(text)} | {dotted}


PY_ROOT = ROOT / "apps/oneapp"
PY_IMPORT = re.compile(
	r"""^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))""", re.M)


def _module(path: pathlib.Path) -> str:
	return str(path.relative_to(PY_ROOT).with_suffix("")).replace("/", ".")


def python_importers() -> dict[str, set[pathlib.Path]]:
	"""Who imports each Python module, by dotted name.

	The same idea as the SPA's graph and for the same reason: most modules here
	whitelist nothing — `email/threading.py`, `spaceview/guard.py` — so their own
	names appear in no spec. What a browser can see them through is whatever
	*endpoint* uses them, which is one hop up this graph.

	Relative imports are resolved against the importing module's package, which
	is how half of `onespace` refers to its neighbours.
	"""
	back: dict[str, set[pathlib.Path]] = {}
	for path in PY_ROOT.rglob("*.py"):
		package = _module(path).rsplit(".", 1)[0]
		text = path.read_text(errors="ignore")
		for absolute, plain in PY_IMPORT.findall(text):
			name = absolute or plain
			if not name:
				continue
			if name.startswith("."):
				name = f"{package}{name}"
			back.setdefault(name, set()).add(path)
		# `from . import mailbox` and `from .scope import _held` both name a
		# sibling without spelling the package, and the regex above sees only
		# the dots. Cheap and good enough: every sibling of a module that does
		# this is a candidate importer.
		for sibling in re.findall(r"^\s*from\s+\.\s+import\s+([\w, ]+)", text, re.M):
			for one in sibling.split(","):
				back.setdefault(f"{package}.{one.strip()}", set()).add(path)
	return back


def python_reached(seeds: set[pathlib.Path]) -> set[pathlib.Path]:
	"""A module and everything that imports it, all the way to an endpoint."""
	back = python_importers()
	seen = set(seeds)
	queue = list(seeds)
	while queue:
		one = queue.pop()
		for who in back.get(_module(one), ()):
			if who not in seen:
				seen.add(who)
				queue.append(who)
	return seen


def specs() -> list[pathlib.Path]:
	return sorted(E2E.glob("*.spec.js"))


# --------------------------------------------------------------------------- #
# The answer
# --------------------------------------------------------------------------- #

def affected(paths: list[str]) -> tuple[list[str], str]:
	"""The specs to run, and one line saying why."""
	interesting = [p for p in paths if not _matches(p, IGNORED)]
	if not interesting:
		return [], "nothing a browser can see changed"

	for path in interesting:
		if _matches(path, SHARED):
			return ["all"], f"{path} is shared, so anything can break"

	wanted: set[pathlib.Path] = set()
	seeds: set[pathlib.Path] = set()
	names: set[str] = set()
	unattributed: list[str] = []

	for path in interesting:
		full = ROOT / path
		if path.startswith("apps/oneapp/frontend/e2e/") and path.endswith(".spec.js"):
			wanted.add(full)
		elif path.startswith("apps/oneapp/frontend/src/") and full.exists():
			seeds.add(full)
		elif path.startswith("apps/oneapp/frontend/src/") and not full.exists():
			# Gone. What it provided is in git, and a spec that named any of it
			# is a spec that can no longer find it.
			was = at_head(path)
			if was is None:
				unattributed.append(path)
			else:
				names |= names_in(full, was)
		elif path.startswith("apps/oneapp/") and path.endswith(".py") and full.exists():
			# The module and everything that imports it: a helper is seen through
			# whichever endpoint uses it, never through its own name.
			for one in python_reached({full}):
				names |= python_tokens(one)
			# And onwards through the SPA: the module's endpoints are called by
			# a `lib/` file, whose own importers are the components a spec can
			# see. Without this hop a server-only change reaches no component.
			seeds |= {
				one for one in list(SRC.rglob("*.js")) + list(SRC.rglob("*.vue"))
				if any(token in one.read_text(errors="ignore") for token in names)
			}
		else:
			unattributed.append(path)

	if unattributed:
		return ["all"], f"{unattributed[0]} is not something this can attribute"

	# A `lib/` module is reached by name rather than by import: everything goes
	# through the barrel, so `mailAway` is the link and `import` is not.
	for one in list(seeds):
		# `lib/workspace/mail.js` is reached as `workspace.mailAway`, never by
		# its own path: the barrel above it is what components import. The
		# directory names the object, which is the convention the whole `lib/`
		# tree follows.
		if "/lib/" in str(one) and one.name != "index.js":
			seeds |= callers(one.parent.name, members_of(one))

	for one in reached(seeds):
		names |= tokens_of(one)

	for spec in specs():
		text = spec.read_text(errors="ignore")
		if any(token in text for token in names):
			wanted.add(spec)

	# Nothing matched, and something in the app changed: that is an absence of
	# evidence rather than evidence of absence — a module whose names no spec
	# happens to write down, reached through something this does not model. It
	# narrows on evidence and never on silence.
	if not wanted:
		return ["all"], "the change matches no spec, which is not the same as none"

	found = sorted(str(one.relative_to(SPA)) for one in wanted)
	return found, f"{len(names)} names, {len(found)} specs"


def main() -> int:
	against = sys.argv[1] if len(sys.argv) > 1 else None
	paths = changed(against)
	found, why = affected(paths)

	print(f"# {why}", file=sys.stderr)
	for one in found:
		print(one)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
