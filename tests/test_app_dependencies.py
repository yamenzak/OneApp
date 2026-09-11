"""Declared Frappe compatibility.

Frappe Cloud reads [tool.bench.frappe-dependencies] at build time and refuses to
deploy an app whose range excludes the bench's version. A ceiling set too low
fails the build with "Incompatible app version found" — after the bench group is
already created, which is an annoying place to discover it.

develop is currently 17.x, so the range has to admit it.

The other half of this file is what may *not* be in that table. Every app named
there has to be installed on the bench, in range, before ours may be — press and
bench both read it as a requirement rather than as a statement of compatibility
— so an app we merely work with belongs nowhere near it.
"""

import tomllib
from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent
APPS = ["oneapp", "oneapp_control"]

# Frappe Cloud compares against versions like "17.0.0-dev"; normalised here to
# what packaging accepts.
SUPPORTED = ["15.0.0", "16.0.0", "17.0.0.dev0"]


def deps(app: str) -> dict:
	data = tomllib.loads((ROOT / "apps" / app / "pyproject.toml").read_text())
	return data.get("tool", {}).get("bench", {}).get("frappe-dependencies", {})


@pytest.mark.parametrize("app", APPS)
def test_declares_a_frappe_range(app):
	assert "frappe" in deps(app), f"{app} declares no frappe dependency"


@pytest.mark.parametrize("app", APPS)
@pytest.mark.parametrize("version", SUPPORTED)
def test_range_admits_supported_versions(app, version):
	spec = SpecifierSet(deps(app)["frappe"])
	assert spec.contains(Version(version), prereleases=True), (
		f"{app} would be refused on frappe {version}: {spec}"
	)


def test_a_new_tenant_site_gets_hrms():
	"""What a bench is assumed to carry when press cannot be asked.

	One place now rather than two. It used to be a field on the Shard *and* a
	fallback string in the provisioning step, which had to agree and were
	checked here because they might not. Both are gone: press is asked what the
	bench group carries at the moment a site is created, and this list is only
	what a screen shows while Frappe Cloud is briefly unreachable.

	A tenant that came up without HRMS has no payroll and nothing says why, so
	the assumption still has to be the full one.
	"""
	steps = (ROOT / "apps/oneapp_control/oneapp_control/provisioning/steps.py").read_text()

	assert 'ASSUMED_APPS = ("frappe", "erpnext", "hrms", "oneapp")' in steps
	assert "records.apps_of" in steps, (
		"the app list is no longer read off the bench group, so it is a copy again"
	)


@pytest.mark.parametrize("app", APPS)
def test_nothing_but_frappe_is_required(app):
	"""Naming an app here is requiring it, whatever the range says.

	This was the bug. `oneapp` named erpnext and hrms, which is
	`required_apps = ["erpnext"]` by another name — the thing hooks.py removed
	on purpose, because nothing in this app imports either at module level.
	Press enforces it the way bench does, so installing oneapp was refused on
	the control bench, which carries frappe, oneapp_control and oneapp and must
	never carry ERPNext, and on any tenant group where oneapp was added before
	the other two.

	What a tenant site installs is `apps_for_site`'s answer, not this table's.
	"""
	named = set(deps(app)) - {"frappe"}
	assert not named, (
		f"{app} requires {', '.join(sorted(named))} on every bench it is installed "
		"on. A range here is a requirement, not a statement of compatibility — "
		"what a space needs goes in its manifest's `requires_apps`."
	)


@pytest.mark.parametrize("app", APPS)
def test_range_has_an_upper_bound(app):
	"""Unbounded would deploy onto a major we have never run."""
	assert "<" in deps(app)["frappe"], f"{app} has no upper bound on frappe"
