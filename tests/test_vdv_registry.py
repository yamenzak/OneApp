"""The VDV shelf, and the two ways a registry like this goes wrong.

It goes wrong by **drifting from the code** — a row saying 457-3 is read after
the reader was renamed, which is a product lying about itself to the one
person who asked a direct question. And it goes wrong by **flattering
itself** — every row `read`, no row `unknown`, which is the same lie with
better manners.

So these check the registry against `sniff`, against `sources`, and against
its own rules, and one of them insists the gaps are still there.
"""

import sys

import pytest


@pytest.fixture
def vdv(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import vdv as module

	return module


def test_every_row_is_shaped_the_same(vdv):
	seen = set()
	for one in vdv.PARTS:
		assert one["part"] not in seen, f"{one['part']} is listed twice"
		seen.add(one["part"])

		assert one["door"] in (vdv.FOLDER, vdv.STREAM, vdv.VEHICLE)
		assert one["state"] in ("read", "recognised", "declared", "unknown")
		assert one["title"], f"{one['part']} has no title"

		# A row claiming to be read has to name the module that reads it, and
		# a row that names one has to claim it.
		if one["state"] == "read":
			assert one["reader"], f"{one['part']} is read by nothing"
		if one["reader"]:
			assert one["state"] == "read"

		# `unknown` is the one state allowed to say nothing about content, and
		# every other state has to say something.
		if one["state"] == "unknown":
			assert not one["carries"]
			assert one["note"], "an admitted gap says why it is one"
		else:
			assert one["carries"], f"{one['part']} says nothing about what it carries"

		# A verified row was written with the document open, so it can point
		# at it. An unverified one is the set to re-read before writing a
		# parser, and saying so is the whole value of the flag.
		if one["verified"]:
			assert one["spec"].startswith("https://www.vdv.de/"), (
				f"{one['part']} claims verified and names no document"
			)


def test_the_registry_and_the_loader_table_cannot_drift(vdv):
	"""Two lists of which formats have a reader is one too many."""
	from oneapp.onemobility import sources

	for format, module in vdv.readers().items():
		assert sources.LOADERS[format] == module

	# And every VDV entry in the loader table came from here rather than
	# being typed beside it.
	for format in sources.LOADERS:
		if format.startswith("VDV"):
			assert format in vdv.FORMATS, f"{format} loads but is not on the shelf"


def test_a_stream_part_never_reaches_the_folder_loader(vdv):
	"""`sources.deliver` calls `<module>.load(feed, content)`. `streaming.py`
	has no such function — it is reached by the dialect a Stream source
	declares — so a 454 document saved into a drop folder must be refused
	rather than dispatched into a stack trace."""
	from oneapp.onemobility import sources

	streamed = [one["part"] for one in vdv.PARTS if one["door"] == vdv.STREAM]
	for format, part in vdv.FORMATS.items():
		if part in streamed:
			assert format not in sources.LOADERS, (
				f"{format} arrives over a subscription and cannot be loaded "
				"from a folder"
			)

	# Every module the folder loaders name is one that exists and exposes
	# `load` — which is the half of the contract a registry cannot state.
	import importlib

	for module in sources.LOADERS.values():
		loaded = importlib.import_module(f"oneapp.onemobility.{module}")
		assert callable(getattr(loaded, "load", None)), f"{module}.load is missing"


def test_everything_sniff_can_name_is_on_the_shelf(vdv):
	"""A delivery identified as a format nobody has written down is a
	customer being told a word with nothing behind it."""
	from oneapp.onemobility import sniff

	named = set(sniff.ROOTS.values()) | set(sniff.HINTS.values())
	for format in named:
		if not format.startswith("VDV") and format != "NeTEx":
			continue
		assert format in vdv.FORMATS, f"`sniff` says {format} and the shelf does not"


def test_ibis_ip_is_marked_as_arriving_through_the_vehicle(vdv):
	"""The distinction the whole table exists for. 301 is device-to-device on
	one bus; a workspace only ever sees it through a bridge, and a row saying
	otherwise would promise a parser where the work is a fleet."""
	for one in vdv.PARTS:
		if one["family"] == "IBIS-IP":
			assert one["door"] == vdv.VEHICLE, f"{one['part']} is not a file"


def test_the_shelf_still_admits_what_it_does_not_know(vdv):
	"""A registry where everything is `read` is a registry nobody should
	believe. This fails when a gap is quietly deleted rather than closed."""
	states = {one["state"] for one in vdv.PARTS}
	assert "unknown" in states or "declared" in states

	unverified = [one["part"] for one in vdv.PARTS if not one["verified"]]
	assert unverified, (
		"every row verified is a claim worth doubting — README §1 says the VDV "
		"specifics are written from working understanding unless read"
	)


def test_coverage_is_a_read_a_reader_may_make(vdv):
	"""It is shipped knowledge rather than the workspace's data, but it still
	sits behind the permission for the screen it draws."""
	import inspect

	body = inspect.getsource(vdv.coverage)
	assert "has_permission" in body and "PermissionError" in body
