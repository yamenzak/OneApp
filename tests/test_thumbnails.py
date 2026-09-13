"""A small picture of a file, and the three things about it worth holding.

**A thumbnail is a nicety and never a failure.** Every path that cannot produce
one has to answer empty and let the card draw the file's format mark. That is
what makes the optional decoders optional: a site with no PyMuPDF and no ffmpeg
shows marks where the pictures would be, and installing either turns them on
with no code change and no migration. A path that raised instead would make a
missing decoder look like a broken Drive.

**The permission check comes first.** Before the kind is read, before the
object is touched. Otherwise the endpoint answers "that is a video" about a
file the caller may not open, which is a small leak and a real one.

**Both ends agree about which kinds can have one.** The browser holds the list
so a card for a `.zip` never makes the request, and the server holds it so a
caller that asks anyway is refused the work. Two copies of a list drift, and
this is the pair that would drift silently — the symptom is a wasted round trip
per card, which nobody notices.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STORAGE = ROOT / "apps/oneapp/oneapp/onestorage"
FRONTEND = ROOT / "apps/oneapp/frontend/src"


@pytest.fixture
def thumbnails(stub_frappe):
	from oneapp.onestorage import thumbnails as module

	return module


# --------------------------------------------------------------------------- #
# One list of what can have a picture
# --------------------------------------------------------------------------- #

def test_python_and_the_browser_agree_about_what_can_have_a_thumbnail(thumbnails):
	js = (FRONTEND / "modules/onestorage/lib/art.js").read_text()
	pattern = re.search(r"export const THUMBNAILED = \[([^\]]+)\]", js)
	assert pattern, "art.js no longer declares which kinds can have a thumbnail"

	browser = set(re.findall(r"'([^']+)'", pattern.group(1)))
	assert browser == set(thumbnails.THUMBNAILED)


def test_every_kind_it_names_is_a_kind_the_server_assigns(thumbnails):
	"""A list naming `Photo` would be a list that never matches anything: the
	column holds what `kinds.py` put there and nothing else."""
	from oneapp.onestorage import kinds

	assert set(thumbnails.THUMBNAILED) <= set(kinds.KINDS)


# --------------------------------------------------------------------------- #
# It fails by drawing nothing
# --------------------------------------------------------------------------- #

def test_a_decoder_that_is_not_installed_is_not_an_error(thumbnails):
	"""`_from_pdf` returns `None` where PyMuPDF is absent rather than raising,
	and `_from_video` does the same where ffmpeg is not on the path. This reads
	the source rather than the behaviour because the point is the *shape*: a
	`return None` beside the import, not an exception somebody has to catch
	somewhere else."""
	source = (STORAGE / "thumbnails.py").read_text()

	pdf = source[source.index("def _from_pdf("):source.index("def _from_video(")]
	assert "except ImportError:" in pdf and "return None" in pdf

	video = source[source.index("def _from_video("):]
	assert "shutil.which(\"ffmpeg\")" in video
	assert "if not ffmpeg:" in video and "return None" in video


class Doc(dict):
	"""A `File` as `render` uses one: `.get()` for the kind, `.name` for the log.

	Attribute access included, because a Frappe Document has it and code that
	had to be defensive about a shape it never sees would be code written for
	this file rather than for the product.
	"""

	__getattr__ = dict.get


def test_a_file_that_cannot_be_decoded_draws_its_mark(thumbnails):
	"""`render` swallows, logs and answers `None`. What reaches this is a
	truncated upload, a format Pillow was built without, an encrypted PDF — and
	for the card's purposes they are one case."""
	# `r2.contents` will raise on this: there is no site, no bucket and no file.
	assert thumbnails.render(Doc(name="FILE-1", custom_kind="Image")) is None


def test_a_kind_with_no_picture_is_answered_without_touching_storage(thumbnails):
	"""An archive and a spreadsheet get `None` from `render` before anything
	tries to read their bytes. The browser should never ask, and asking anyway
	must still be cheap."""
	for kind in ("Sheet", "Doc", "Code", "Other", "Audio", "Document"):
		assert thumbnails.render(Doc(name="FILE-1", custom_kind=kind)) is None


# --------------------------------------------------------------------------- #
# The permission check comes first
# --------------------------------------------------------------------------- #

def test_permission_is_checked_before_the_row_is_read_for_anything_else():
	"""Derived from frappe/suite, whose comment says why: "Permission first, so
	callers can't probe type/existence of files they can't read." Read out of
	the source in order, because the ordering *is* the property — a test that
	only asserted a refusal would pass with the check at the bottom."""
	source = (STORAGE / "thumbnails.py").read_text()
	body = source[source.index("def thumbnail("):source.index("def render(")]

	permission = body.index("frappe.has_permission")
	assert permission < body.index("is_folder"), (
		"the kind is read before the permission is checked, so the endpoint "
		"answers questions about files the caller may not open"
	)
	assert permission < body.index("render(")


def test_the_answer_is_private():
	"""These are somebody's drawings. A shared proxy that kept one would hand it
	to the next reader through it."""
	source = (STORAGE / "thumbnails.py").read_text()
	assert 'response_headers["Cache-Control"] = f"private' in source
	assert "public" not in source[source.index("MAX_AGE ="):source.index("THUMBNAILED =")]
