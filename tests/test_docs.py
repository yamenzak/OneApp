"""A document, over the file table every attachment already lives in.

Four things are worth holding here, and the first is the one the design rests
on — the same one a sheet rests on.

**A document is a `File`.** Not a doctype of its own, so its permission, its
folder, its share, its bin and its link are all things that already existed.
Every read and write in `onedoc` goes through the File, and a path
that did not would be a path with no access model at all.

**Two blobs go up and only one is authoritative.** `content` is the ProseMirror
JSON the editor reads back; `html` is what search, the preview and every export
read. Deriving the second from the first in Python would mean a ProseMirror
implementation in Python, so the editor sends both.

**Which files the editor opens is one list, said twice** — once in Python and
once in JavaScript, because the browser decides whether a click routes without
asking. Two copies of the same list drift.

**A template is a document with a flag on it**, the same shape a sheet template
is. One shape rather than two: a person who has made one already knows how to
make the other.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "apps/oneapp/oneapp/onedoc"
SHEETS = ROOT / "apps/oneapp/oneapp/onesheet"
FRONTEND = ROOT / "apps/oneapp/frontend/src"


@pytest.fixture
def docs(stub_frappe):
	from oneapp import onedoc as module

	return module


# --------------------------------------------------------------------------- #
# A document is a File
# --------------------------------------------------------------------------- #

#: The ones that do not ask a File in so many words, each for a stated reason.
#: `make` and `make_text` ask the *record* they attach to, checked below;
#: `listing` is a `get_list`, which is Frappe's own permission check and is
#: checked below too.
ASKS_SOMETHING_ELSE = {"make", "make_text", "listing"}


def test_every_entry_point_goes_through_the_file(docs):
	"""The File is the whole access model, so an endpoint that never touches
	one is an endpoint with none."""
	for path in sorted(DOCS.glob("*.py")):
		source = path.read_text()
		for name in re.findall(r"@frappe\.whitelist\([^)]*\)\n(?:@\w[\w.]*\n)*def (\w+)\(", source):
			if name in ASKS_SOMETHING_ELSE:
				continue
			block = source[source.index(f"def {name}("):]
			head = block[:block.index("\n\n\n")] if "\n\n\n" in block else block
			assert "_mine(" in head or "check_permission" in head or "get_doc(\"File\"" in head, (
				f"docs.{name} never asks a File whether it may"
			)


def test_making_one_against_a_record_asks_that_record(docs):
	"""Attaching to a record you cannot change is how a document ends up on
	somebody else's quotation."""
	source = (DOCS / "writing.py").read_text()
	assert "def _may_attach(" in source
	for name in ("def make(", "def make_text("):
		block = source[source.index(name):]
		assert "_may_attach(" in block[:block.index("frappe.get_doc({")]


def test_the_package_re_exports_everything_it_whitelists(docs):
	"""`oneapp.onedoc.save_doc` has to resolve, or it is a 404.

	A whitelisted function inside a package module is not reachable by the
	package's own path unless the package re-exports it.
	"""
	source = "\n".join(p.read_text() for p in sorted(DOCS.glob("*.py")))
	for name in re.findall(r"@frappe\.whitelist\([^)]*\)\n(?:@\w[\w.]*\n)*def (\w+)\(", source):
		assert hasattr(docs, name), (
			f"docs.{name} is whitelisted but not re-exported — it would 404"
		)


def test_a_documents_file_url_is_a_url_the_framework_accepts(docs):
	"""`File.validate` refuses a row whose URL names nothing, and its own
	exception for bytes that are produced rather than stored is a
	`/api/method/` URL. A document's bytes are produced."""
	assert docs.ROUTE.startswith("/api/method/")
	assert docs.url_for("abc123").startswith("/api/method/")
	assert "abc123" in docs.url_for("abc123")


def test_a_documents_prose_goes_when_its_file_does(docs):
	"""Without this the bin's sweep leaves the body of every document anybody
	ever threw away."""
	source = (DOCS / "writing.py").read_text()
	block = source[source.index("def on_trash("):]
	assert "Doc Body" in block
	hooks = (ROOT / "apps/oneapp/oneapp/hooks.py").read_text()
	assert "onedoc.on_trash" in hooks


# --------------------------------------------------------------------------- #
# One list of what the editor opens
# --------------------------------------------------------------------------- #

def test_python_and_the_browser_agree_about_what_opens_in_the_editor(docs):
	"""A `.md` the browser routes to the editor and the server calls "not text"
	is a page that loads and then says the file cannot be opened.

	Both sides now build the same union — the plain kinds plus every language in
	the catalogue — so what is checked here is the *plain* half. The language
	half is `tests/test_onecode.py`, which reads the two catalogues back against
	each other.
	"""
	js = (FRONTEND / "lib/files/files.js").read_text()
	pattern = re.search(r"const PLAIN = \[([^\]]+)\]", js)
	assert pattern, "files.js no longer declares the plain text extensions"

	browser = set(re.findall(r"'([^']+)'", pattern.group(1)))
	python = set(docs.EDITABLE) - set(_catalogue()["EXTENSIONS"])
	# The two Python spells `markdown` as an alias and the browser reaches
	# through the catalogue for.
	assert browser == python - {"md", "markdown"}


def _catalogue() -> dict:
	source = ROOT / "apps/oneapp/oneapp/onecode/languages.py"
	namespace = {}
	exec(compile(source.read_text(), str(source), "exec"), namespace)
	return namespace


def test_one_function_decides_whether_a_click_routes(docs):
	"""Two lists drift, and the one that drifted was the record's Files tab: it
	previewed sheets long after the Drive had learnt not to."""
	deciding = []
	for path in sorted((FRONTEND).rglob("*.vue")):
		if "custom_kind === 'Sheet'" in path.read_text():
			deciding.append(path.relative_to(FRONTEND).as_posix())
	assert deciding == [], (
		f"{deciding} decides for itself what a click opens — use routeFor() "
		"for where it goes, or editorFor() for which editor to mount"
	)


# --------------------------------------------------------------------------- #
# Templates, in the shape sheets already have
# --------------------------------------------------------------------------- #

def test_a_template_is_the_same_flag_on_both(docs):
	"""One shape rather than two. A second column would be a second listing, a
	second menu and a second thing to explain."""
	from oneapp import onesheet as sheets

	assert docs.TEMPLATE_FIELD == sheets.TEMPLATE_FIELD == "custom_is_template"


def test_making_a_template_is_a_write_and_not_a_share(docs):
	"""Whether anybody else can see it is the share, which already exists."""
	source = (DOCS / "templates.py").read_text()
	block = source[source.index("def set_template("):]
	assert 'check_permission("write")' in block


def test_the_listing_is_a_get_list(docs):
	"""A template is a File, a File may be shared or not, and `get_all` would
	hand somebody every template on the site."""
	source = (DOCS / "templates.py").read_text()
	assert "frappe.get_list(" in source
	assert "frappe.get_all(" not in source


def test_the_editor_is_told_whether_this_is_a_template(docs):
	"""Returned by `get_doc` rather than scanned out of the listing: the sheet
	page has to scan because its editor is vendored and never sees the File.
	This one is ours."""
	source = (DOCS / "body.py").read_text()
	block = source[source.index("def get_doc("):]
	assert '"is_template"' in block[:block.index("\n\n\n")]

	editor = (FRONTEND / "components/docs/DocEditor.vue").read_text()
	assert "docSetTemplate" in editor
