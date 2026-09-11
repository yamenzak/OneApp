"""A shard is a bench group, and Frappe Cloud knows the rest.

Adding capacity used to mean filling eight required fields, six of which press
already holds — which is how the first real deployment's shard asked what to
fill and answered a wrong guess with a 500. These hold the form to the shape
the audit argued for: one question an operator can answer, and derivations for
everything that is somebody else's fact.
"""

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHARD = ROOT / "apps/oneapp_control/oneapp_control/control_plane/doctype/shard/shard.json"
REGION = ROOT / "apps/oneapp_control/oneapp_control/control_plane/doctype/region/region.json"
LOGIC = ROOT / "apps/oneapp_control/oneapp_control/control_plane/doctype/shard/shard.py"


def fields(path) -> dict:
	return {f["fieldname"]: f for f in json.loads(path.read_text())["fields"]}


def test_the_bench_group_is_the_only_press_field_required():
	"""Everything else is an answer, so it must not be a question."""
	shard = fields(SHARD)
	assert shard["press_release_group"].get("reqd")
	for derived in ("press_server", "press_cluster", "region", "press_site_plan"):
		assert not shard[derived].get("reqd"), (
			f"{derived} is filled from press; requiring it asks for something "
			"the operator has no way to answer"
		)


def test_the_derivations_exist():
	"""A field that stopped being required and is not filled is a blank field."""
	body = LOGIC.read_text().split("def fill_from_press")[1].split("\n\tdef ")[0]
	for derived in ("press_server", "press_cluster", "region", "press_site_plan"):
		assert f"self.{derived} =" in body or f'self.get("{derived}")' in body, (
			f"{derived} is optional and nothing fills it"
		)


def test_deploy_ring_is_gone():
	"""It said exactly what `accepts_new_tenants` says.

	Canary excluded a shard from allocation and Wave 1, Wave 2 and Fleet were
	indistinguishable to every query — a four-value Select doing a checkbox's
	job, and two ways to exclude a shard that had to agree.
	"""
	assert "deploy_ring" not in fields(SHARD)
	assert "accepts_new_tenants" in fields(SHARD)

	allocator = LOGIC.read_text()
	live = "\n".join(
		line for line in allocator.splitlines() if not line.strip().startswith("#")
	)
	assert "deploy_ring" not in live, "the allocator still reads a field that is gone"


def test_a_region_remembers_which_cluster_it_is():
	region = fields(REGION)
	assert "press_cluster" in region
	assert region["press_cluster"].get("read_only"), (
		"press's answer, not ours — typing it is how the two drift"
	)


# --------------------------------------------------------------------------- #
# The sync
# --------------------------------------------------------------------------- #

@pytest.fixture
def regions(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp_control.provisioning.regions"):
			del sys.modules[name]
	from oneapp_control.provisioning import regions as module

	return module


def test_the_sync_never_deletes(regions):
	"""A region a customer chose is a region tenants are sitting in, and press
	dropping a cluster from one group's list is not evidence it is gone."""
	source = pathlib.Path(regions.__file__).read_text()
	assert "delete" not in source.lower().split('"""', 2)[2], (
		"the sync must only ever create"
	)


def test_a_new_region_is_inactive(regions):
	"""Country drives the chart of accounts and is not press's to answer, so a
	region press invented must not be offered before somebody says."""
	source = pathlib.Path(regions.__file__).read_text()
	assert '"is_active": 0' in source


def test_press_saying_nothing_is_not_a_reason_to_change_anything(regions, monkeypatch):
	monkeypatch.setattr(regions.records, "groups", lambda: [])
	assert regions.sync_from_press()["ok"] is False


def test_clusters_come_from_what_a_bench_group_can_reach(regions, monkeypatch):
	"""Not from every cluster press has: one no bench group reaches is one we
	cannot place a tenant in, whatever press thinks."""
	monkeypatch.setattr(regions.records, "groups", lambda: [{"name": "rg-1"}, {"name": "rg-2"}])
	monkeypatch.setattr(
		regions.records, "regions_of",
		lambda name: [{"name": "eu-central"}] if name == "rg-1" else [{"cluster": "us-east"}],
	)
	assert regions.clusters() == {"eu-central", "us-east"}


def test_an_unbacked_region_is_reported_and_not_touched(regions, monkeypatch):
	monkeypatch.setattr(regions, "clusters", lambda: {"eu-central"})
	monkeypatch.setattr(
		regions.frappe, "get_all",
		lambda *a, **kw: [
			{"name": "nuremberg", "press_cluster": "eu-central"},
			{"name": "virginia", "press_cluster": "us-east"},
		],
	)
	assert regions.unbacked() == ["virginia"]


def test_attention_reads_it(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp_control.attention"):
			del sys.modules[name]
	from oneapp_control import attention

	assert "regions" in dict(attention.CHECKS)


def test_the_sync_is_scheduled(stub_frappe):
	source = (
		ROOT / "apps/oneapp_control/oneapp_control/hooks.py"
	).read_text()
	assert "oneapp_control.provisioning.regions.scheduled_run" in source
