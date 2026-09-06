"""No sentence a customer reads is stuck in English.

The rule is one line — a string the reader can see is inside `__()` — and the
whole of the interesting part is in `tests/copy_reader.py`, which knows what
"a string the reader can see" means and can tell a wrapped one from a bare one.

`i18n_todo.txt` is the ratchet. It lists the files that still carry bare
strings, and the only edit it may ever receive is a deletion: a file that
appears in it may still fail, a file that does not must pass, and a file with
nothing left in it has to leave. That is what makes a pass this size safe to do
over several sittings without the guard being switched off in between — the
number only goes down, and the day it reaches zero the file goes with it.

Why `__()` and not a key: see `docs/LANGUAGE.md`. The msgid is the English
sentence, which is why this guard can read the sentence out of the call and
hand it to `test_ui_copy` unchanged.
"""

import pathlib

import pytest
from copy_reader import ROOT, sources, unwrapped, visible

TODO = pathlib.Path(__file__).parent / "i18n_todo.txt"


def still_owed() -> set[str]:
	return {
		line.strip()
		for line in TODO.read_text().splitlines()
		if line.strip() and not line.startswith("#")
	}


def test_the_reader_still_finds_the_copy():
	"""A scan that matches nothing passes for the wrong reason."""
	assert len(visible()) > 900, "the copy scan matched almost nothing"


def test_every_sentence_a_customer_reads_is_translatable():
	guilty = {}
	owed = still_owed()
	for where, text in unwrapped():
		if where in owed:
			continue
		guilty.setdefault(where, []).append(text)

	assert not guilty, "these are stuck in English — wrap them in `__()`:\n" + "\n".join(
		f"  {where}: {', '.join(repr(one) for one in texts[:4])}"
		+ (f" and {len(texts) - 4} more" if len(texts) > 4 else "")
		for where, texts in sorted(guilty.items())
	)


def test_the_ratchet_only_goes_down():
	"""A file listed as owing nothing is a line that should have been deleted.

	Without this the list is a place to hide a file rather than a record of
	what is left: adding a name would silence the guard for it for ever.
	"""
	owing = {where for where, _ in unwrapped()}
	stale = sorted(still_owed() - owing)
	assert not stale, (
		"these no longer carry a bare string and must come out of "
		f"tests/i18n_todo.txt:\n  " + "\n  ".join(stale)
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
