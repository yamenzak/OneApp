"""A space's front page, and why it is made of that space's own screens.

The page itself is four lines of shaping. What is worth pinning is the
argument: a block is a *screen*, so it inherits that screen's columns, count
and permissions — and role-specificity falls out of that rather than out of a
role → layout table somebody has to maintain beside the roles themselves.

Every test here is about a way that could quietly stop being true. A block
resolved against the whole screen list rather than the navigable one would put
a door in front of somebody who is then refused at it. A block naming a
component screen would draw an empty table where a map was meant to be. And a
home declared last in a manifest is a home nobody lands on.
"""

import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOMEPAGE = ROOT / "apps/oneapp/oneapp/onespace/homepage.py"
RESOLVE = ROOT / "apps/oneapp/oneapp/onespace/spaceview/resolve.py"
SPACES = ROOT / "apps/oneapp_control/oneapp_control/spaces"


@pytest.fixture(scope="module")
def homepage():
	import sys

	sys.path.insert(0, str(ROOT / "apps/oneapp/oneapp/onespace"))
	import importlib.util

	spec = importlib.util.spec_from_file_location("homepage_only", HOMEPAGE)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


SCREENS = [
	{"screen": "deals", "label": "Deals", "singular": "Deal",
	 "icon": "lucide-shopping-cart", "document_type": "Opportunity"},
	{"screen": "leads", "label": "Leads", "document_type": "Lead"},
	{"screen": "network", "label": "Network", "document_type": "Transit Line",
	 "component": "onemobility/network"},
]


def test_a_block_is_a_screen_and_carries_its_own_name(homepage):
	found = homepage.shape({"blocks": ["deals"]}, SCREENS)
	assert found["blocks"] == [{
		"screen": "deals", "label": "Deals", "singular": "Deal",
		"icon": "lucide-shopping-cart",
	}]


def test_a_name_that_is_not_a_screen_costs_its_own_block(homepage):
	"""An empty block is a thing somebody reports as broken; a missing one is a
	manifest somebody fixes."""
	found = homepage.shape({"blocks": ["deals", "nonsense", "leads"]}, SCREENS)
	assert [one["screen"] for one in found["blocks"]] == ["deals", "leads"]


def test_a_screen_with_no_records_behind_it_is_not_a_block(homepage):
	"""A map, a wizard, another Configuration page. A block is a short list;
	those are destinations, and the rail is where a destination goes."""
	assert homepage.shape({"blocks": ["network"]}, SCREENS) == {}


def test_a_page_with_no_blocks_is_no_page(homepage):
	for asked in (None, {}, {"blocks": "deals"}, {"blocks": []}):
		assert homepage.shape(asked, SCREENS) == {}


def test_a_home_is_a_glance_rather_than_a_report(homepage):
	"""Six blocks and five rows each. Past that the rail is two inches away."""
	assert homepage.BLOCKS == 6
	found = homepage.shape({"blocks": ["deals"] * 20}, SCREENS)
	assert len(found["blocks"]) == homepage.BLOCKS
	assert found["rows"] == homepage.ROWS


def test_role_specific_means_resolved_against_the_navigable_screens():
	"""The whole argument, and it is one line in the resolver.

	`navigable` narrows a space's screens to the seat, so a block whose screen
	this reader cannot open is never sent — rather than sent and then refused
	at the door. Against the full list this page would be the same for
	everybody and would lie about it.
	"""
	source = RESOLVE.read_text()
	at = source.index("if resolved[\"component\"] == homepage.HOME:")
	block = source[at:source.index("return resolved", at)]
	assert "navigable(space)" in block, (
		"a home's blocks are resolved against every screen, so it is the same "
		"page for everybody"
	)


def _home_of(name: str) -> dict | None:
	"""The home screen a manifest declares, read out of the source."""
	tree = ast.parse((SPACES / f"{name}.py").read_text())
	for node in ast.walk(tree):
		if not isinstance(node, ast.Dict):
			continue
		keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
		if "screen" not in keys:
			continue
		values = dict(zip(keys, node.values))
		screen = values.get("screen")
		if isinstance(screen, ast.Constant) and screen.value == "home":
			return values
	return None


WITH_A_HOME = ("oneproject", "onecrm", "onemobility")


@pytest.mark.parametrize("space", WITH_A_HOME)
def test_the_home_is_the_first_screen_a_space_declares(space):
	"""Or it is not the page anybody lands on: opening a space with no screen
	in the URL renders the first one."""
	source = (SPACES / f"{space}.py").read_text()
	first = re.search(r'"screen": "([\w-]+)"', source[source.index("SCREENS = ["):])
	assert first.group(1) == "home", f"{space} lands somewhere else"


@pytest.mark.parametrize("space", WITH_A_HOME)
def test_every_block_a_space_names_is_a_screen_it_has(space):
	"""The engine drops one that is not, which is right and silent. This is the
	half that says so out loud, at the one moment somebody can act on it."""
	source = (SPACES / f"{space}.py").read_text()
	declared = set(re.findall(r'"screen": "([\w-]+)"', source))

	home = _home_of(space)
	assert home is not None
	settings = ast.literal_eval(home["view_settings"].args[0])
	blocks = settings["home"]["blocks"]
	assert blocks, f"{space} declares a home with nothing on it"
	missing = set(blocks) - declared
	assert not missing, f"{space}'s home names screens it does not have: {sorted(missing)}"
	assert json.dumps(blocks)
