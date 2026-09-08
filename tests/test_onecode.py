"""One language catalogue, and two copies of it that have to agree.

The server decides what `New > Code` may create and what the Drive calls a
`.py`; the SPA decides what the picker offers and what CodeMirror colours. A
language on one side and not the other is either a button that throws or a file
nobody can make, and neither announces itself — the first is a 417 somebody
hits once a month, the second is silence.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PY_SIDE = ROOT / "apps/oneapp/oneapp/onecode/languages.py"
JS_SIDE = ROOT / "apps/oneapp/frontend/src/modules/onestorage/lib/languages.js"


@pytest.fixture(scope="module")
def catalogue():
	namespace = {}
	exec(compile(PY_SIDE.read_text(), str(PY_SIDE), "exec"), namespace)
	return namespace


def _js_block(name: str) -> str:
	"""One `export const NAME = {…}` or `[…]` body out of the JavaScript.

	Read rather than parsed: it is a flat literal of string keys and string
	values, and a JavaScript parser to check twenty lines would be a second
	thing to keep working.
	"""
	source = JS_SIDE.read_text()
	start = source.index(f"export const {name} = ")
	opened = source.index("{" if "{" in source[start:start + 60] else "[", start)
	closer = "}" if source[opened] == "{" else "]"
	depth, index = 0, opened
	while True:
		if source[index] == source[opened]:
			depth += 1
		elif source[index] == closer:
			depth -= 1
			if depth == 0:
				return source[opened:index + 1]
		index += 1


def _js_keys(name: str) -> set:
	body = _js_block(name)
	# Keys are bare identifiers at the start of a line; values are quoted and
	# never look like this, which is what makes the anchor safe.
	return set(re.findall(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*):", body, re.M))


def test_both_sides_know_the_same_languages(catalogue):
	assert set(catalogue["LANGUAGES"]) == _js_keys("LANGUAGES")


def test_both_sides_know_the_same_aliases(catalogue):
	assert set(catalogue["ALIASES"]) == _js_keys("ALIASES")


def test_every_alias_points_at_a_language_that_exists(catalogue):
	unknown = {
		key: target
		for key, target in catalogue["ALIASES"].items()
		if target not in catalogue["LANGUAGES"]
	}
	assert not unknown, f"these aliases name nothing: {unknown}"


def test_the_same_languages_are_offered_on_both_sides(catalogue):
	js = re.search(r"export const NOT_OFFERED = \[([^\]]*)\]", JS_SIDE.read_text()).group(1)
	assert set(re.findall(r"'([^']+)'", js)) == set(catalogue["NOT_OFFERED"])


def test_every_highlight_is_one_frappe_ui_can_load(catalogue):
	"""The keys `loadLanguage` takes, and nothing invented beside them.

	A typo here is not an error anywhere: `loadLanguage` returns null for an
	unknown key, so the file opens uncoloured and looks like a language we
	simply do not support.
	"""
	loadable = {
		"json", "html", "javascript", "python", "sql",
		"markdown", "css", "scss", "yaml", "xml",
	}
	wrong = {
		key: value[2]
		for key, value in catalogue["LANGUAGES"].items()
		if value[2] and value[2] not in loadable
	}
	assert not wrong, f"frappe-ui cannot load these: {wrong}"


def test_the_extension_column_is_the_key(catalogue):
	"""The middle column is the extension, and it is the key for all of them.

	It is written out rather than derived so the table reads as a table, which
	is exactly how a copy-pasted row ends up saying `("Rust", "rs", "")` under
	the key `go`.
	"""
	wrong = {
		key: value[1]
		for key, value in catalogue["LANGUAGES"].items()
		if value[1] != key
	}
	assert not wrong, f"these rows disagree with their own key: {wrong}"
