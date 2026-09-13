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


# --------------------------------------------------------------------------- #
# The rails a tenant project runs on — `docs/UNIFICATION.md` §E9
# --------------------------------------------------------------------------- #
#
# Four guards, and §E9 names them. Each is here because the thing it catches
# fails somewhere a person cannot see it: an engine that will not resolve fails
# in the browser, a route collision fails on whichever of two pages the router
# reached first, and a `context_script` does not fail at all.

import sys

sys.path.insert(0, str(ROOT / "apps/oneapp"))

from oneapp.onecode import engines, manifest, routes  # noqa: E402

ENGINES_JS = ROOT / "apps/oneapp/frontend/src/modules/onecode/lib/engines.js"

GOOD = {
	"name": "Storefront", "route": "shop", "engine": "preact",
	"entry": "main.js", "reads": ["Item"], "calls": [],
}


def test_a_project_declares_its_context_and_never_writes_one():
	"""§E9's first guard, and the reason the section exists before the arc.

	`Web Page.context_script` is a Python field that runs with the framework in
	scope. It is exactly what a tenant app needs and exactly what a tenant may
	never have — so a manifest carrying one is refused by name, with the reason,
	rather than ignored.
	"""
	for key in manifest.REFUSED:
		with pytest.raises(manifest.Invalid) as raised:
			manifest.validate({**GOOD, key: "anything"})
		assert key in str(raised.value)

	# And the whole of the context really is built from the declaration.
	built = manifest.context(manifest.validate(GOOD), reader="someone@example.com")
	assert set(built) == {
		"project", "route", "engine", "entry", "reads", "calls", "imports", "user",
	}
	assert built["reads"] == ["Item"]


def test_a_project_may_not_call_its_way_around_the_declaration():
	"""A declared method is one of ours, and not every one of ours."""
	with pytest.raises(manifest.Invalid):
		manifest.validate({**GOOD, "calls": ["frappe.client.get_list"]})
	for never in manifest.NEVER_CALLED:
		with pytest.raises(manifest.Invalid):
			manifest.validate({**GOOD, "calls": [f"{never}.anything"]})


def test_an_entry_is_a_file_inside_the_project():
	"""The traversal this had for ten minutes: `lstrip("./")` strips every
	leading dot and slash there is, so `../../etc/passwd.js` arrived as
	`etc/passwd.js` and passed both the `..` check and the pattern."""
	for entry in ("../../etc/passwd.js", "/abs/main.js", "a/../b.js", "main.png"):
		with pytest.raises(manifest.Invalid):
			manifest.validate({**GOOD, "entry": entry})
	assert manifest.validate({**GOOD, "entry": "./src/main.mjs"})["entry"] == "src/main.mjs"


def test_a_route_cannot_be_one_of_ours():
	"""§E9's second guard. Claiming `/one` does not shadow the SPA — Frappe's
	own router wins — so the failure is a page that silently never loads."""
	for reserved in routes.RESERVED:
		with pytest.raises(routes.Collision):
			routes.validate(f"/{reserved}")
		with pytest.raises(routes.Collision):
			routes.validate(f"/{reserved}/deeper")


def test_a_route_cannot_be_another_project_s():
	"""Checked at save time, and on segments rather than on the string.

	`startswith` would say `/shop` contains `/shopping`, which is a claim
	refused for no reason; segments say it does not and that `/shop/admin` is
	the one that collides.
	"""
	taken = {"shop": "Storefront"}
	assert routes.check("shopping", taken) == "shopping"
	for colliding in ("shop", "/shop/", "shop/admin", "shop/admin/users"):
		with pytest.raises(routes.Collision) as raised:
			routes.check(colliding, taken)
		assert "Storefront" in str(raised.value)


def test_every_entry_in_the_import_map_is_pinned_and_ours():
	"""§E9's third guard. A range is a project that worked on Tuesday; a
	third-party CDN makes every tenant page's integrity somebody else's
	operational decision."""
	for key, (label, version, files) in engines.ENGINES.items():
		if key == "none":
			assert not files, "the engine that is no engine carries no imports"
			continue
		assert re.match(r"^\d+\.\d+\.\d+$", version), f"{key} is pinned to “{version}”"
		for specifier, file in files.items():
			assert "://" not in file, f"{key}:{specifier} is served from another host"
			# The version is in the filename, so two projects on two versions
			# are two files rather than one file that changed under one of them.
			assert re.search(r"\d+\.\d+\.\d+", file), f"{file} does not name a version"

	for key in engines.OFFERED:
		mapped = engines.import_map(key)["imports"]
		assert all(url.startswith(engines.ROOT + "/") for url in mapped.values())


def test_the_picker_offers_exactly_the_engines_the_map_carries():
	"""§E9's fourth guard, and the language catalogue's own bug one layer out:
	an engine the picker offers and the map does not carry is a project that
	saves and will not load."""
	source = ENGINES_JS.read_text()
	offered = re.findall(r"\{ value: '([\w-]+)', label: [^\n]*?version: '([\d.]*)'", source)
	assert offered, "the picker's list did not parse"
	assert [key for key, _ in offered] == list(engines.OFFERED)
	for key, version in offered:
		assert version == engines.version(key), f"{key}: picker says {version}"


def test_a_manifest_that_does_not_parse_says_where():
	with pytest.raises(manifest.Invalid) as raised:
		manifest.parse("{ nope }")
	assert "line 1" in str(raised.value)
	with pytest.raises(manifest.Invalid):
		manifest.parse("[]")
