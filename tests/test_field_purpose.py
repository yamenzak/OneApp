"""Every field has to do something, and say honestly what.

Three failures found by auditing the whole control surface field by field, all
of them silent, and each one a class rather than a one-off:

  * a setting an operator can change that nothing reads. `bucket_max_tenants`
    promised to be the rotation threshold for new R2 buckets and was wired to
    nothing at all — an operator narrowing the blast radius to 50 tenants a
    bucket got buckets that still took 200, with no error and no clue.
    `credits_per_currency_unit` was the same shape and had simply been
    outlived by the Credit Pack catalogue.

  * a control whose value is discarded. `Tenant.environment` is overwritten
    from the shard on every save, so the Select on the workspace form was one
    an operator could set and never keep.

  * a field that is only written. The lifecycle sweep recorded what it did
    every night onto a Single that, on a site with no desk, nothing could
    read — so the one thing about the ladder worth watching was invisible.

These pin all three so the next one fails here rather than in production.
"""

import ast
import json
import re
from pathlib import Path

import pytest

from doctype_paths import slug as doctype_slug

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "apps/oneapp_control/oneapp_control"
SETTINGS = CONTROL / "entitlements/settings.py"


def doctype(name: str, app: str = "oneapp_control", module: str = "control_plane") -> dict:
	s = doctype_slug(name)
	path = ROOT / "apps" / app / app / module / "doctype" / s / f"{s}.json"
	return json.loads(path.read_text())


def field(name: str, fieldname: str, **kw) -> dict:
	for f in doctype(name, **kw)["fields"]:
		if f["fieldname"] == fieldname:
			return f
	raise AssertionError(f"{name} has no field {fieldname}")


def control_sources() -> dict[str, str]:
	"""Every Python file of the control plane except the settings form itself."""
	return {
		p.relative_to(ROOT).as_posix(): p.read_text()
		for p in CONTROL.rglob("*.py")
		if p != SETTINGS and "__pycache__" not in p.parts
	}


# --------------------------------------------------------------------------- #
# A setting nothing reads
# --------------------------------------------------------------------------- #

def offered_settings() -> list[str]:
	"""The fieldnames `entitlements/settings.py` puts in front of an operator.

	Read out of the source rather than by importing it, because the module
	wants a Frappe site and this question does not.
	"""
	tree = ast.parse(SETTINGS.read_text())
	names = []
	for node in ast.walk(tree):
		if not isinstance(node, ast.Call):
			continue
		fn = node.func
		if getattr(fn, "id", None) != "_setting" or not node.args:
			continue
		first = node.args[0]
		if isinstance(first, ast.Constant) and isinstance(first.value, str):
			names.append(first.value)
	return names


def test_the_reader_found_the_settings_form():
	offered = offered_settings()
	assert len(offered) > 20, f"only found {len(offered)} settings — the form moved"
	assert "press_api_key" in offered and "cold_retention_days" in offered


@pytest.mark.parametrize("fieldname", offered_settings())
def test_every_offered_setting_is_read_somewhere(fieldname):
	"""A settings field is a promise that changing it changes something.

	`bucket_max_tenants` broke that promise for as long as it existed: it
	described itself as the rotation threshold and `provision_bucket` never
	looked at it. Nothing in the readiness board covers this, because from the
	outside a setting that is stored and ignored looks exactly like one that
	works.
	"""
	pattern = re.compile(r"\b" + re.escape(fieldname) + r"\b")
	readers = [path for path, src in control_sources().items() if pattern.search(src)]
	assert readers, (
		f"the settings dialog offers {fieldname!r}, and nothing outside the "
		f"dialog reads it — an operator can set it and nothing happens. Wire "
		f"it up or take it off the form."
	)


def test_a_new_bucket_carries_the_configured_cap():
	"""The specific one, at the line that was missing it."""
	r2 = (CONTROL / "cloudflare/r2.py").read_text()
	assert "def _bucket_cap()" in r2, "the cap is no longer read from settings"
	assert '"bucket_max_tenants"' in r2
	created = r2[r2.index("def provision_bucket"):]
	assert "_bucket_cap()" in created, (
		"provision_bucket no longer stamps the configured cap onto the bucket, "
		"so lowering it in settings does nothing again"
	)


# --------------------------------------------------------------------------- #
# A control whose value is discarded
# --------------------------------------------------------------------------- #

DERIVED = [
	# doctype, field, what derives it
	("Tenant", "environment", "inherit_environment_from_shard"),
]


@pytest.mark.parametrize("name,fieldname,deriver", DERIVED)
def test_a_derived_field_is_not_offered_as_a_control(name, fieldname, deriver):
	"""`read_only` is a real guard here, not decoration.

	`spaceview._writable` keeps only fields marked editable, and a read-only
	field is never editable — so this both stops the form drawing a control and
	stops a hand-made payload writing through it. Which matters, because the
	value would be silently replaced on the very next save anyway.
	"""
	controller = (CONTROL / "control_plane/doctype" / doctype_slug(name)
	              / f"{doctype_slug(name)}.py").read_text()
	assert f"def {deriver}(" in controller, (
		f"{deriver} is gone — is {name}.{fieldname} still derived?"
	)
	assert field(name, fieldname).get("read_only"), (
		f"{name}.{fieldname} is derived by {deriver} on every save, so an "
		f"editable control over it is one whose value is thrown away"
	)


def test_the_workspaces_signing_secret_is_not_a_form_field():
	"""`ensure_hmac_secret` fills a blank and keeps whatever is already there,
	so a typo into this box would stick — and every signed call from that site
	would start failing its signature with nothing to point at."""
	assert field("Tenant", "hmac_secret").get("read_only")


def test_where_a_workspaces_data_lives_is_fixed_at_signup():
	"""A bucket is allocated once and kept for life. Editing this afterwards
	moved no objects; it only made the cold-copy manifest claim a jurisdiction
	that was not the one the files were in."""
	assert field("Tenant", "storage_jurisdiction").get("set_only_once")


# --------------------------------------------------------------------------- #
# A field that is only ever written
# --------------------------------------------------------------------------- #

def test_the_sweeps_own_status_is_readable():
	"""The ladder suspends, archives and deletes on a timer. "Did it run last
	night" is the question, and the answer was in a read-only field on a Single
	on a site with no desk — written every night, reachable by nobody."""
	setup = (CONTROL / "api/setup.py").read_text()
	assert '"key": "lifecycle_sweep"' in setup, "the sweep check is gone"
	for fieldname in ("lifecycle_swept_on", "lifecycle_note"):
		assert fieldname in setup, f"the check no longer reads {fieldname}"


# --------------------------------------------------------------------------- #
# Types that carry a promise
# --------------------------------------------------------------------------- #

def test_a_regions_country_is_picked_and_required():
	"""It is not a label. It rides the sync payload into every workspace created
	in the region, names its Company, and selects its chart of accounts by exact
	string match in `books._charts_for`. Free text meant a typo produced a
	workspace whose books quietly never got set up; optional meant an empty one
	did the same."""
	country = field("Region", "country")
	assert country["fieldtype"] == "Link" and country["options"] == "Country"
	assert country.get("reqd"), (
		"without a country, `books.ensure_setup` returns 'not enough known' and "
		"every workspace in this region opens Books to a manual setup"
	)


def test_the_two_stripe_currencies_stay_free_text():
	"""The inverse guard, because these look exactly like the bug above.

	`Plan.currency` is a Link to Currency and an operator picks it. These two
	hold *Stripe's* code for the same thing, and Stripe is lowercase (`usd`)
	while Frappe's Currency records are uppercase (`USD`) — so a Link here
	fails validation on every row. `Subscription Add-on.currency` is written
	by `_reconcile_addons` inside the Stripe webhook, which is the one path
	that must never throw.
	"""
	catalogue = (CONTROL / "billing/catalogue.py").read_text()
	assert ".lower()" in catalogue, (
		"catalogue.py no longer lowercases the currency — if Stripe's casing "
		"stopped being the reason these are Data, they can become Links"
	)
	for name in ("Catalogue Price", "Subscription Add-on"):
		assert field(name, "currency")["fieldtype"] == "Data", (
			f"{name}.currency became a Link; it holds Stripe's lowercase code "
			f"and every row would fail link validation"
		)


def test_a_usage_rows_provider_is_the_same_closed_list_the_model_carries():
	"""`pricing` copies `model.provider` straight onto the row, so the two hold
	the same two values. As Data it was a standard filter rendering a free-text
	box over a two-item list."""
	model = field("AI Model", "provider")
	usage = field("AI Usage Record", "provider")
	assert usage["fieldtype"] == "Select"
	assert usage["options"] == model["options"], (
		f"the two lists have drifted: {usage['options']!r} vs {model['options']!r}"
	)
