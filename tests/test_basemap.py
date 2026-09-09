"""What a map is drawn on, and who gets to decide.

Three parties have a say and they do not have an equal one: the instance, which
may have been pointed at its own tile store or told to fetch nothing at all; the
workspace, which picks between the curated styles; and the reader's own screen,
which is only ever asked whether it is dark. These pin the order, because the
failure mode of getting it wrong is a map that draws — just not the one anybody
chose, which is the kind of wrong nobody reports.
"""

import sys

import pytest

@pytest.fixture
def basemap(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]
	from oneapp.onespace import basemap as module

	return module


class Row(dict):
	def get(self, key, default=None):
		return dict.get(self, key, default)


def workspace(stub_frappe, **fields):
	"""Say what `OneSpace Map Settings` holds on this site, or that it is absent."""
	stub_frappe.db.records[("DocType", "OneSpace Map Settings")] = bool(fields)
	stub_frappe.get_cached_doc = lambda *a, **k: Row(fields)


def test_a_bench_that_says_nothing_gets_the_quiet_vector_style(basemap, stub_frappe):
	stub_frappe.conf = {}
	workspace(stub_frappe)
	out = basemap.boot()
	assert out["style"] == basemap.DEFAULT_STYLE
	assert not out["plain"]


def test_the_control_plane_has_no_settings_table_and_still_draws(basemap, stub_frappe):
	"""`OneSpace Map Settings` is a tenant doctype and the control site renders
	the same boot payload. A missing table is an ordinary state here, not a
	broken one."""
	stub_frappe.conf = {}
	stub_frappe.db.records[("DocType", "OneSpace Map Settings")] = False
	assert basemap.chosen() == basemap.DEFAULTS
	assert basemap.boot()["style"] == basemap.DEFAULT_STYLE


def test_a_workspace_picks_between_the_curated_styles(basemap, stub_frappe):
	stub_frappe.conf = {}
	workspace(stub_frappe, map_style="Bright", map_labels=1, map_detail="Full")
	out = basemap.boot()
	assert out["style"] == basemap.STYLES["Bright"]
	assert out["pick"] == "Bright"
	assert out["labels"] is True
	assert out["detail"] == "Full"


def test_an_instance_that_named_a_style_keeps_it(basemap, stub_frappe):
	"""An operator who has pointed a bench at their own tile store did so for a
	reason, and a customer picking Bright must not send them back off it."""
	stub_frappe.conf = {"oneapp_map_style": "https://tiles.internal/style.json"}
	workspace(stub_frappe, map_style="Bright")
	assert basemap.boot()["style"] == "https://tiles.internal/style.json"


def test_the_instance_answer_is_sent_alongside_the_resolved_one(basemap, stub_frappe):
	"""So a picker can put "Follow the instance" back without a page reload: the
	payload it loaded with has the workspace's pick baked into `style`."""
	stub_frappe.conf = {}
	workspace(stub_frappe, map_style="Liberty")
	out = basemap.boot()
	assert out["style"] == basemap.STYLES["Liberty"]
	assert out["instance"] == basemap.DEFAULT_STYLE


def test_the_picker_and_the_doctype_offer_the_same_styles(basemap):
	"""Two lists of the same names, in two languages, and only one of them is
	validated against — so a style added to `STYLES` and not to the Select is
	one nobody can reach, and the other way round is a Select entry that throws
	when it is chosen."""
	import json
	import os

	here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	with open(os.path.join(here, "apps/oneapp/oneapp/onespace/doctype/"
	                             "onespace_map_settings/onespace_map_settings.json"),
	          encoding="utf-8") as handle:
		field = next(one for one in json.load(handle)["fields"]
		             if one["fieldname"] == "map_style")
	offered = field["options"].split("\n")
	assert offered == ["Follow the instance", *basemap.STYLES, "Plain"]


def test_our_own_style_is_a_file_this_app_serves(basemap):
	"""It is a path rather than a URL, and that is the difference that matters:
	the other three are documents somebody else writes and serves."""
	assert basemap.STYLES["Canvas"] == "/assets/oneapp/basemaps/canvas.json"
	import os

	here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	assert os.path.exists(os.path.join(
		here, "apps/oneapp/oneapp/public/basemaps/canvas.json"))


def test_the_styles_are_sent_by_name_and_url(basemap, stub_frappe):
	stub_frappe.conf = {}
	workspace(stub_frappe)
	assert basemap.boot()["styles"] == basemap.STYLES


def test_an_instance_may_refuse_third_party_tiles_outright(basemap, stub_frappe):
	stub_frappe.conf = {"oneapp_map_plain": True}
	workspace(stub_frappe, map_style="Bright")
	out = basemap.boot()
	assert out["plain"] and out["style"] == "" and out["tiles"] == ""
	assert basemap.hosts() == ()


def test_a_workspace_may_refuse_them_for_itself(basemap, stub_frappe):
	"""The air-gapped instance's setting, made available to one customer on a
	shared one."""
	stub_frappe.conf = {}
	workspace(stub_frappe, map_style="Plain")
	assert basemap.boot()["plain"]


def test_a_style_credits_itself_and_is_not_credited_twice(basemap, stub_frappe):
	"""Every style here names a TileJSON that carries the full linked
	attribution, and MapLibre draws it. Sending ours alongside it stacked two
	credits into one line saying the same thing twice, once less completely."""
	stub_frappe.conf = {}
	workspace(stub_frappe, map_style="Bright")
	assert basemap.boot()["attribution"] == ""


def test_a_raster_template_has_no_document_to_credit_it(basemap, stub_frappe):
	"""A tile template is a URL and nothing else, so a credit is needed and this
	is the minimum true of any OSM-derived store."""
	stub_frappe.conf = {"oneapp_map_tiles": "https://tiles.internal/{z}/{x}/{y}.png"}
	workspace(stub_frappe)
	assert basemap.boot()["attribution"] == basemap.DEFAULT_ATTRIBUTION


def test_an_operator_who_names_a_credit_always_gets_it(basemap, stub_frappe):
	"""They may be serving tiles nobody else knows the provenance of."""
	stub_frappe.conf = {"oneapp_map_attribution": "© The Ordnance Survey"}
	workspace(stub_frappe, map_style="Bright")
	assert basemap.boot()["attribution"] == "© The Ordnance Survey"


def test_a_raster_bench_is_still_a_raster_bench(basemap, stub_frappe):
	"""The vector default must not quietly override a configured tile template:
	a style URL and a tile template are different things and only one of them
	was configured."""
	stub_frappe.conf = {"oneapp_map_tiles": "https://tiles.internal/{z}/{x}/{y}.png"}
	workspace(stub_frappe)
	out = basemap.boot()
	assert out["style"] == ""
	assert out["tiles"] == out["dark"] == "https://tiles.internal/{z}/{x}/{y}.png"


def test_only_the_default_host_is_named_in_a_clause(basemap, stub_frappe):
	"""A clause is published; a workspace's morning is not. Every curated style
	is the same host, so switching between them changes nothing a clause says —
	and an operator's own tile store is theirs to disclose."""
	stub_frappe.conf = {}
	workspace(stub_frappe, map_style="Bright")
	assert basemap.hosts() == basemap.DEFAULT_HOSTS
	stub_frappe.conf = {"oneapp_map_style": "https://tiles.internal/style.json"}
	assert basemap.hosts() == ()
	stub_frappe.conf = {"oneapp_map_tiles": "https://tiles.internal/{z}/{x}/{y}.png"}
	assert basemap.hosts() == ()


def test_only_an_admin_may_change_it(basemap, stub_frappe):
	stub_frappe.get_roles = lambda *a: ["Sales User"]
	with pytest.raises(stub_frappe.PermissionError):
		basemap.set_basemap(style="Bright")


def test_a_style_nobody_ships_is_refused(basemap, stub_frappe):
	stub_frappe.get_roles = lambda *a: ["OneSpace Workspace Owner"]
	saved = Row()
	stub_frappe.get_doc = lambda *a, **k: saved
	with pytest.raises(stub_frappe.ValidationError):
		basemap.set_basemap(style="Stamen Watercolor")
	with pytest.raises(stub_frappe.ValidationError):
		basemap.set_basemap(detail="Whatever")
