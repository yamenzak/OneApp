"""The usage-meter contract.

`UsageBar.vue` is generated into both apps and rendered from three different
server payloads: the tenant's own quota module, the tenant's session endpoint,
and the control plane's customer overview. Nothing connects them but the key
names, and a mismatch does not fail — the bar renders at zero on a full site,
which is worse than an error because it reads as good news.

So the component is parsed for the keys it reads, and each producer is checked
against them.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
USAGE_BAR = ROOT / "apps/oneapp/frontend/src/components/UsageBar.vue"
TENANT_QUOTA = ROOT / "apps/oneapp/oneapp/oneapp_core/storage/quota.py"
CONTROL_CUSTOMER = ROOT / "apps/oneapp_control/oneapp_control/api/customer.py"


def keys_read_by_component() -> set[str]:
	"""Every `usage.<key>` / `u.<key>` the component dereferences."""
	source = USAGE_BAR.read_text()
	found = set(re.findall(r"\b(?:props\.usage|usage|u)\??\.([a-z_]+)", source))
	# `usage` is also the prop name itself in `props.usage`; that is not a key.
	return found - {"usage", "value"}


def keys_returned_by(path: Path, function: str) -> set[str]:
	"""Literal string keys of the dict a named function returns."""
	tree = ast.parse(path.read_text())
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name == function:
			for inner in ast.walk(node):
				if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Dict):
					return {
						k.value
						for k in inner.value.keys
						if isinstance(k, ast.Constant) and isinstance(k.value, str)
					}
	raise AssertionError(f"no dict-returning {function}() in {path}")


def test_component_still_reads_recognisable_keys():
	# If this shrinks to nothing the regex has stopped matching and every
	# assertion below would pass vacuously.
	assert keys_read_by_component() >= {"fraction", "warn", "exceeded", "used", "quota"}


@pytest.mark.parametrize("function", ["usage_summary", "database_summary"])
def test_tenant_summaries_satisfy_the_component(function):
	missing = keys_read_by_component() - keys_returned_by(TENANT_QUOTA, function)
	assert not missing, f"{function}() is missing {sorted(missing)}"


def test_control_overview_satisfies_the_component():
	# usage_for() builds its buckets through a nested helper.
	tree = ast.parse(CONTROL_CUSTOMER.read_text())
	buckets = {
		k.value
		for node in ast.walk(tree)
		if isinstance(node, ast.FunctionDef) and node.name == "bucket"
		for inner in ast.walk(node)
		if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Dict)
		for k in inner.value.keys
		if isinstance(k, ast.Constant) and isinstance(k.value, str)
	}
	assert buckets, "no bucket() returning a dict in customer.py"
	missing = keys_read_by_component() - buckets
	assert not missing, f"bucket() is missing {sorted(missing)}"


def test_both_apps_ship_the_same_component():
	control = ROOT / "apps/oneapp_control/frontend/src/components/UsageBar.vue"
	assert control.read_text() == USAGE_BAR.read_text()
