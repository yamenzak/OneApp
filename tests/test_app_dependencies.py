"""Declared Frappe compatibility.

Frappe Cloud reads [tool.bench.frappe-dependencies] at build time and refuses to
deploy an app whose range excludes the bench's version. A ceiling set too low
fails the build with "Incompatible app version found" — after the bench group is
already created, which is an annoying place to discover it.

develop is currently 17.x, so the range has to admit it.
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


def test_oneapp_declares_hrms_too():
	"""Payroll, leave balances and attendance come from HRMS, and a tenant bench
	that carries it has to be admitted by the range or press refuses the build.

	Not `required_apps`, for the same reason erpnext is not one — see hooks.py.
	A range says "this works with"; a requirement says "this will not start
	without", and the second is false.
	"""
	assert "hrms" in deps("oneapp")

	spec = SpecifierSet(deps("oneapp")["hrms"])
	for version in SUPPORTED:
		assert spec.contains(Version(version), prereleases=True), (
			f"oneapp would be refused on hrms {version}: {spec}"
		)


def test_a_new_tenant_site_gets_hrms():
	"""The default a shard is created with, and the fallback in `site_apps`.

	Two places, and they have to agree: a shard whose field is empty falls back
	to the string in the provisioning step, and one created today takes the
	doctype's default. A tenant that came up without HRMS has no payroll and
	nothing says why."""
	steps = (ROOT / "apps/oneapp_control/oneapp_control/provisioning/steps.py").read_text()
	schema = (ROOT / "apps/oneapp_control/oneapp_control/control_plane/doctype/"
	          "shard/shard.json").read_text()

	assert '"frappe,erpnext,hrms,oneapp"' in steps
	assert '"frappe,erpnext,hrms,oneapp"' in schema


def test_oneapp_requires_erpnext():
	"""oneapp declares required_apps = ['erpnext'], so the range must exist too."""
	assert "erpnext" in deps("oneapp")


@pytest.mark.parametrize("version", SUPPORTED)
def test_erpnext_range_tracks_frappe(version):
	spec = SpecifierSet(deps("oneapp")["erpnext"])
	assert spec.contains(Version(version), prereleases=True), (
		f"oneapp would be refused on erpnext {version}: {spec}"
	)


@pytest.mark.parametrize("app", APPS)
def test_range_has_an_upper_bound(app):
	"""Unbounded would deploy onto a major we have never run."""
	assert "<" in deps(app)["frappe"], f"{app} has no upper bound on frappe"
