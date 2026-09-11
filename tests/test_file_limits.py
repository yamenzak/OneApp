"""A number that lives on both sides of the wire lives in two files.

`onedoc/text.py` refuses to open a text file over two megabytes, and the Drive
has to know that *before* it mounts an editor — otherwise it mounts one and the
editor says "that document did not open" into a pane that could have said what
the file is, how big it is, and offered the download.

So the SPA carries the same ceiling, and this holds the two to each other. The
alternative — sending the limit down in the boot payload — is a round trip and
a new field for a constant that changes about once.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def python_ceiling() -> int:
	source = (ROOT / "apps/oneapp/oneapp/onedoc/text.py").read_text()
	found = re.search(r"^MAX_BYTES\s*=\s*(\d+)\s*\*\s*(\d+)\s*\*\s*(\d+)", source, re.M)
	assert found, "onedoc/text.py no longer declares MAX_BYTES as a product"
	return int(found.group(1)) * int(found.group(2)) * int(found.group(3))


def spa_ceiling() -> int:
	source = (ROOT / "apps/oneapp/frontend/src/modules/onestorage/lib/files.js").read_text()
	found = re.search(r"TEXT_CEILING\s*=\s*(\d+)\s*\*\s*(\d+)\s*\*\s*(\d+)", source)
	assert found, "files.js no longer declares TEXT_CEILING as a product"
	return int(found.group(1)) * int(found.group(2)) * int(found.group(3))


def test_the_two_ceilings_are_the_same_number():
	assert spa_ceiling() == python_ceiling(), (
		"the Drive would offer an editor the server then refuses, or refuse one "
		"it would have opened"
	)


def test_the_drive_checks_it_before_choosing_an_editor():
	"""Not after. A refusal the editor reports is a refusal with no details in
	it, which is the whole complaint this answers."""
	source = (ROOT / "apps/oneapp/frontend/src/modules/onestorage/lib/files.js").read_text()
	body = source.split("export function editorFor")[1].split("\n}")[0]
	assert "TEXT_CEILING" in body

	# And the two kinds that are rows in our own tables are exempt: a sheet's
	# bytes are a CSV the grid reads, not a file an editor holds in memory.
	before = body.split("TEXT_CEILING")[0]
	assert "'Sheet'" in before and "'Doc'" in before


def test_the_previewer_says_which_refusal_it_is():
	"""A `.docx` has no preview at any size, and telling somebody it is too big
	invites them to try a smaller one."""
	source = (
		ROOT / "apps/oneapp/frontend/src/modules/onestorage/components/FileSurface.vue"
	).read_text()
	assert "readable.value && oversize.value" in source
	assert "data-slot=\"file-details\"" in source
