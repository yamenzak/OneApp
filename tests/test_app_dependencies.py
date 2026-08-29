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
