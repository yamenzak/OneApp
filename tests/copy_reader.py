"""Every string a customer can read, found once and shared.

Three guards ask the same question of the same set — is this sentence about the
plumbing (`test_ui_copy`), is it inside `__()` (`test_i18n`), does it name a
supplier — and three copies of the scan would drift into three different
answers about what "a string the reader can see" means.

It is a regex over source rather than a render, and that is a deliberate
ceiling: it finds strings in the places strings go — a prop that puts words on
screen, a text node between tags — and it cannot find one assembled at runtime.
What it does find, it finds in every file, which is the property that matters
for a guard.
"""

import pathlib
import re

from vendored import is_vendored

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Where a customer reads. Everything under `screens/ops/` inside them is the
#: operator console; the callers decide whether that matters to their rule.
SPAS = ("apps/oneapp/frontend/src", "apps/oneapp_control/frontend/src")

#: The props and options that put a string in front of somebody.
ATTRS = ("label", "title", "description", "placeholder", "tooltip", "message",
         "successMessage", "empty", "header", "subtitle", "text")

#: A bare text node between tags: `>Save changes<`. Twelve characters and an
#: initial capital, because shorter than that is as often a variable name, an
#: icon or a unit as it is a sentence. `{}` is excluded, so a node that has
#: been wrapped — `>{{ __('Save changes') }}<` — does not match this and is
#: found by TRANSLATED instead.
TEXT_NODE = re.compile(r">\s*([A-Z][^<>{}\n]{12,})\s*<")

#: The same sentence after it has been wrapped: `__('…')` anywhere. The copy
#: rules apply to a translated string exactly as they did to a bare one — the
#: msgid *is* the English sentence — so a scan that stopped finding them the
#: day they were wrapped would be a scan that quietly stopped working.
TRANSLATED = re.compile(r"__\(\s*['\"]([^'\"]{3,})['\"]")


def strip_comments(text: str) -> str:
	"""Comments out, and only comments.

	The lookbehind is the whole of the second line: `accept="image/*"` opens
	nothing, and without it that attribute swallowed everything up to the next
	`*/` — which in `drive/CameraCapture.vue` was thirty lines including the
	file's own `import { __ }`, so a file that translated read as one that did
	not. A real block comment is preceded by a newline or a space; one written
	tight against a word or inside a string is not one we need to find.
	"""
	text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
	text = re.sub(r"(?<![\w\"'=/])/\*.*?\*/", "", text, flags=re.S)
	return re.sub(r"^\s*//.*$", "", text, flags=re.M)


def sources():
	"""Every file of ours in either SPA, as (where, text)."""
	for spa in SPAS:
		base = ROOT / spa
		for path in sorted(base.rglob("*.vue")) + sorted(base.rglob("*.js")):
			if is_vendored(path):
				continue
			# A fixture is not copy. `foo.test.js` writes `{text: 'Already
			# written.'}` because that is what the server would have sent, and
			# wrapping it in `__()` would be translating a test's own data —
			# the sentence is never rendered anywhere.
			if path.name.endswith(".test.js"):
				continue
			yield f"{spa}/{path.relative_to(base)}", strip_comments(path.read_text())


def unwrapped() -> list[tuple[str, str]]:
	"""Every string the reader can see that is **not** inside `__()`.

	The patterns only match the bare forms, which is what makes this the
	i18n guard rather than a second copy of it: `label="Save"` matches and
	`:label="__('Save')"` does not, because the lookbehind refuses the `:` a
	bound prop carries and a wrapped value starts with `__(` rather than a
	quote. A wrapped text node carries `{}`, which `TEXT_NODE` excludes.
	"""
	found = []
	for where, raw in sources():
		for attr in ATTRS:
			pattern = rf'(?<![\w:.-]){attr}\s*[=:]\s*["\']([^"\']{{3,}})["\']'
			for m in re.finditer(pattern, raw):
				found.append((where, m.group(1)))
		for m in TEXT_NODE.finditer(raw):
			found.append((where, m.group(1).strip()))
	return found


def visible() -> list[tuple[str, str]]:
	"""Every string the reader can see, wrapped or not.

	What the copy rules are checked against, because they are rules about the
	English sentence and wrapping it does not change the sentence.
	"""
	found = unwrapped()
	for where, raw in sources():
		for m in TRANSLATED.finditer(raw):
			found.append((where, m.group(1)))
	return found


def thrown() -> list[tuple[str, str]]:
	"""Every message the server hands back to a browser."""
	found = []
	for path in sorted((ROOT / "apps").rglob("*.py")):
		if "node_modules" in str(path):
			continue
		where = str(path.relative_to(ROOT))
		for m in re.finditer(r'_\(\s*"([^"]{8,})"', path.read_text()):
			found.append((where, m.group(1)))
	return found
