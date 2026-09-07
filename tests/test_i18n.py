"""No sentence a customer reads is stuck in English.

The rule is one line — a string the reader can see is inside `__()` — and the
whole of the interesting part is in `tests/copy_reader.py`, which knows what
"a string the reader can see" means and can tell a wrapped one from a bare one.

It was done behind a ratchet — `i18n_todo.txt`, a list of the files that still
carried bare strings, which only ever shrank — because 1,224 strings is not one
sitting and a guard switched off for a week is a guard nobody switches back on.
The list reached zero and went with it, which is why this file no longer has a
skip in it: every file passes now, and a new one has to pass on the day it is
written.

Why `__()` and not a key: see `docs/LANGUAGE.md`. The msgid is the English
sentence, which is why this guard can read the sentence out of the call and
hand it to `test_ui_copy` unchanged.
"""

import re

import pytest
from copy_reader import ROOT, sources, unwrapped, visible


def test_the_reader_still_finds_the_copy():
	"""A scan that matches nothing passes for the wrong reason."""
	assert len(visible()) > 900, "the copy scan matched almost nothing"


def test_every_sentence_a_customer_reads_is_translatable():
	guilty = {}
	for where, text in unwrapped():
		guilty.setdefault(where, []).append(text)

	assert not guilty, "these are stuck in English — wrap them in `__()`:\n" + "\n".join(
		f"  {where}: {', '.join(repr(one) for one in texts[:4])}"
		+ (f" and {len(texts) - 4} more" if len(texts) > 4 else "")
		for where, texts in sorted(guilty.items())
	)


def test_an_apostrophe_is_the_one_on_the_keyboard():
	"""`'` and not `\u2019`.

	The curly one is better typography and it is the wrong call here: it is
	invisible in a diff, it is not what anybody types into a search box, and it
	arrived in the first place because a straight apostrophe inside `__('…')`
	has to be escaped and swapping the character looked like the easy way out.
	The easy way out is `__("…")`, which is what these use.
	"""
	guilty = [
		f"{where}: {text}"
		for where, text in visible()
		if "\u2019" in text
	]
	assert not guilty, "use a straight apostrophe, in a double-quoted call:\n  " + "\n  ".join(
		guilty
	)


def test_a_file_that_translates_says_so_at_the_top():
	"""`__` is imported per file rather than made global, so that a file which
	puts words on screen is a file whose imports say it does."""
	missing = [
		where
		for where, raw in sources()
		# The module that defines it is the one file that may say it without
		# importing it.
		if "__(" in raw and "runtime/translate" not in where and "runtime/translate" not in raw
	]
	assert not missing, (
		"these call `__()` without importing it — add "
		"`import { __ } from '@/lib/runtime/translate'`:\n  " + "\n  ".join(sorted(missing))
	)


@pytest.mark.parametrize("half", ["__(", "loadTranslations", "direction"])
def test_the_runtime_is_shared_by_both_apps(half):
	for spa in ("apps/oneapp", "apps/oneapp_control"):
		source = (ROOT / spa / "frontend/src/lib/runtime/translate.js").read_text()
		assert half in source, f"{spa} has no {half}"


def test_english_pays_nothing():
	"""The msgid is the English sentence, so an English reader must not be
	made to fetch a catalogue to be told so."""
	source = (ROOT / "apps/oneapp/frontend/src/lib/runtime/translate.js").read_text()
	assert "lang === 'en'" in source


def test_the_page_is_drawn_the_right_way_round_before_it_is_drawn():
	"""Arabic is not a repaint. `dir` has to be on the document before the app
	mounts, or the whole layout moves after the reader has seen it."""
	main = (ROOT / "apps/oneapp/frontend/src/main.js").read_text()
	assert "documentElement.dir" in main
	assert main.index("documentElement.dir") < main.index("createApp(App)")


@pytest.mark.parametrize("spa", ["apps/oneapp", "apps/oneapp_control"])
def test_nothing_asks_for_a_word_before_the_catalogue_arrives(spa):
	"""`App.vue` is imported *after* the catalogue, not at the top of the file.

	A static import is evaluated before any line of `main.js` runs. So a
	component that builds a table of labels as it is imported — and several do,
	because a `const` beside the component is where a list of options belongs —
	would call `__()` against an empty catalogue and hold the English answer for
	the life of the session. Nothing about that fails loudly: the app works, in
	English, in Arabic.
	"""
	main = (ROOT / spa / "frontend/src/main.js").read_text()
	assert "import App from" not in main, "App.vue is imported before the catalogue"
	assert "import('./App.vue')" in main
	assert main.index("loadTranslations(lang)") < main.index("import('./App.vue')")


@pytest.mark.parametrize("spa", ["apps/oneapp", "apps/oneapp_control"])
def test_a_date_says_its_age_in_the_reader_s_language(spa):
	"""`8 days ago` is not in the catalogue.

	It is built by dayjs's `relativeTime` plugin out of a locale that has to be
	loaded separately, so a page can be translated down to the last button and
	still say the age of every row in English.
	"""
	runtime = (ROOT / spa / "frontend/src/lib/runtime/dates.js").read_text()
	assert "export async function loadDates" in runtime
	# Literal import paths, or the bundler cannot see which locales to ship.
	for lang in ("ar", "de"):
		assert f"import('dayjs/esm/locale/{lang}')" in runtime

	main = (ROOT / spa / "frontend/src/main.js").read_text()
	assert "loadDates(lang)" in main
	assert main.index("loadDates(lang)") < main.index("import('./App.vue')")


# --------------------------------------------------------------------------- #
# The other half: what the server says
# --------------------------------------------------------------------------- #

# A `frappe.throw` is not always copy. Three of these are a programmer's
# assertion reached only by a bad call, and three are an operator's — the
# control plane's desk, which is ours and is English. Each one is exempted by
# hand, and the point of naming them here is that a *new* one has to be argued
# for rather than quietly added.
UNTRANSLATED_ON_PURPOSE = {
	# A feature name that no decorator registered: a bug in our code, not
	# something a customer can cause or fix.
	"apps/oneapp/oneapp/oneapp_core/ai/gateway.py",
	# An action a selection was told to do that no branch implements: same.
	"apps/oneapp/oneapp/oneapp_core/email/mailbox/selections.py",
	# Both of these are read by us, in our own console, about our own fleet.
	"apps/oneapp_control/oneapp_control/portal.py",
	"apps/oneapp_control/oneapp_control/provisioning/runner.py",
}

SPEAKS = {"throw", "msgprint"}


def _called(node):
	import ast

	if isinstance(node, ast.Attribute):
		return node.attr
	if isinstance(node, ast.Name):
		return node.id
	return ""


def _translated(node):
	"""True, False, or None for an expression this cannot judge statically."""
	import ast

	if isinstance(node, ast.Call):
		if _called(node.func) in {"_", "gettext"}:
			return True
		# `_("…").format(…)` and `_("…").join(…)` are still translated.
		if isinstance(node.func, ast.Attribute) and node.func.attr in {"format", "join"}:
			return _translated(node.func.value)
		# Anything else — a helper that builds the sentence somewhere else, like
		# `connect._reason` — is judged where it builds it, not here.
		return None
	if isinstance(node, ast.JoinedStr):  # an f-string can never be a msgid
		return False
	if isinstance(node, ast.Constant):
		return not isinstance(node.value, str)
	if isinstance(node, ast.BinOp):
		return _translated(node.left) and _translated(node.right)
	if isinstance(node, ast.IfExp):
		return _translated(node.body) and _translated(node.orelse)
	return None  # a variable — some other line built it, and is checked there


def test_every_sentence_the_server_says_is_translatable():
	"""`frappe.throw` and `frappe.msgprint` reach the same reader the SPA does.

	Read as a syntax tree rather than with a regex, because the interesting
	case is the one that spans four lines: `frappe.throw(` on its own, then an
	f-string under it, which no grep for `throw(f"` will ever find.
	"""
	import ast

	guilty = []
	for app in ("apps/oneapp/oneapp", "apps/oneapp_control/oneapp_control"):
		for path in sorted((ROOT / app).rglob("*.py")):
			where = str(path.relative_to(ROOT))
			if where in UNTRANSLATED_ON_PURPOSE:
				continue
			try:
				tree = ast.parse(path.read_text())
			except SyntaxError:
				continue
			for node in ast.walk(tree):
				if not isinstance(node, ast.Call) or _called(node.func) not in SPEAKS:
					continue
				if node.args and _translated(node.args[0]) is False:
					guilty.append(f"{where}:{node.lineno}  {ast.unparse(node.args[0])[:70]}")

	assert not guilty, "these speak English at the reader — wrap them in `_()`:\n  " + "\n  ".join(
		guilty
	)


def test_the_exemptions_are_still_needed():
	"""Same ratchet as `i18n_todo.txt`: a name that no longer earns its place
	comes out, or the set becomes somewhere to hide a file."""
	import ast

	for where in sorted(UNTRANSLATED_ON_PURPOSE):
		tree = ast.parse((ROOT / where).read_text())
		bare = [
			node
			for node in ast.walk(tree)
			if isinstance(node, ast.Call)
			and _called(node.func) in SPEAKS
			and node.args
			and _translated(node.args[0]) is False
		]
		assert bare, f"{where} no longer says anything in English — drop it from the set"


def test_both_apps_extract_their_own_messages():
	"""`babel_extractors.csv` beside the app package.

	Frappe's own map sends `**/hooks.py` to the navbar extractor, which
	resolves the file's real path and then asks for it relative to the bench.
	Ours are symlinked into the bench from this repository, so that subtraction
	fails and the whole POT comes out empty — silently, with a zero exit. The
	app's own map is read first, so one row claiming `hooks.py` for the plain
	Python extractor is the whole fix.
	"""
	for app in ("oneapp", "oneapp_control"):
		rows = (ROOT / "apps" / app / "babel_extractors.csv").read_text().splitlines()
		assert "**/hooks.py,frappe.gettext.extractors.python.extract" in rows


# --------------------------------------------------------------------------- #
# The catalogues themselves
# --------------------------------------------------------------------------- #

import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import i18n as catalogue  # noqa: E402

PLACEHOLDER = re.compile(r"\{[^}]*\}")
TAG = re.compile(r"</?\w+>")


@pytest.mark.parametrize("lang", catalogue.LANGUAGES)
def test_nothing_a_customer_reads_is_still_in_english(lang):
	"""Every msgid we own has a translation.

	"We own" is the interesting half and is `scripts/i18n.py`'s answer: what the
	extractor found, minus the strings only an operator sees, minus everything
	Frappe or ERPNext already translates. The last subtraction is why this
	number is a fifth of what it looks like it should be.
	"""
	mine = catalogue.po("oneapp", lang)
	owed = sorted(
		msgid for (msgid, ctx) in catalogue.ours("oneapp", lang) if not mine.get((msgid, ctx))
	)
	assert not owed, (
		f"{len(owed)} strings have no {lang}: run `python3 scripts/i18n.py gap {lang}`\n  "
		+ "\n  ".join(one[:70] for one in owed[:12])
	)


@pytest.mark.parametrize("lang", catalogue.LANGUAGES)
def test_a_translation_carries_the_same_placeholders(lang):
	"""`{0}` is not a word and does not get translated.

	A dropped one is a sentence with a hole where the file name was; an invented
	one is a `KeyError` in front of a customer. Same for the inline tags: a
	`<b>` that lost its `</b>` bolds the rest of the page.
	"""
	guilty = []
	for (msgid, _ctx), msgstr in sorted(catalogue.po("oneapp", lang).items()):
		if not msgstr:
			continue
		if sorted(PLACEHOLDER.findall(msgid)) != sorted(PLACEHOLDER.findall(msgstr)):
			guilty.append(f"placeholders: {msgid[:60]}")
		if sorted(TAG.findall(msgid)) != sorted(TAG.findall(msgstr)):
			guilty.append(f"tags: {msgid[:60]}")
	assert not guilty, f"{lang}.po:\n  " + "\n  ".join(guilty[:12])


@pytest.mark.parametrize("lang", catalogue.LANGUAGES)
def test_we_do_not_shadow_a_translation_somebody_maintains(lang):
	"""A msgid Frappe or ERPNext translates must not be in our file.

	The framework merges every installed app's catalogue with ours last, so
	carrying our own Arabic for `Save` would silently replace forty languages'
	worth of maintained work with one line nobody reviews again.
	"""
	if not (catalogue.BENCH / "frappe/frappe/locale" / f"{lang}.po").exists():
		pytest.skip("no bench to compare against")

	covered = catalogue.upstream(lang)
	ours = sorted(msgid for msgid, _ctx in catalogue.po("oneapp", lang) if msgid in covered)
	assert not ours, (
		f"{lang}.po repeats what upstream already says — `python3 scripts/i18n.py sync` "
		f"drops these:\n  " + "\n  ".join(one[:70] for one in ours[:12])
	)
