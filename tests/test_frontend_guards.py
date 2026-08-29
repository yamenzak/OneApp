"""The frontend guards.

Two SPAs have to look and behave like one product. They cannot share an npm
workspace, since each is mirrored to its own repository for Frappe Cloud, so the
shared setup is generated into both instead. These tests assert the guards that
make that hold.
"""

import json
import sys
from pathlib import Path

import re

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from gen_frontend import APPS, render  # noqa: E402


@pytest.fixture
def generated():
	return {app: render(app, spec) for app, spec in APPS.items()}


def test_both_apps_are_generated(generated):
	assert set(generated) == {"oneapp", "oneapp_control"}


def test_generated_copies_are_on_disk_and_unmodified():
	"""The check CI runs. Editing a copy lets the SPAs drift."""
	import check_frontend

	assert check_frontend.main() == 0


@pytest.mark.parametrize(
	"filename",
	["frontend/src/ui.js", "frontend/src/lib/resource.js", "frontend/src/lib/notify.js",
	 "frontend/src/lib/errors.js", "frontend/src/lib/socket.js", "frontend/src/lib/sound.js"],
)
def test_shared_runtime_is_byte_identical(generated, filename):
	"""Not merely present in both — the same file."""
	contents = {app: files[filename] for app, files in generated.items()}
	assert len(set(contents.values())) == 1, f"{filename} differs between apps"


def test_direct_frappe_ui_imports_are_blocked(generated):
	"""Going direct skips response unwrapping, error parsing and sound."""
	for app, files in generated.items():
		config = files["frontend/eslint.config.js"]
		assert "no-restricted-imports" in config, app
		assert "'frappe-ui'" in config or '"frappe-ui"' in config, app
		assert "socket.io-client" in config, app


def test_the_runtime_itself_is_exempt_from_that_rule(generated):
	"""The wrapper has to import what it wraps."""
	for app, files in generated.items():
		assert "src/lib/**" in files["frontend/eslint.config.js"], app


@pytest.mark.parametrize(
	"element", ["button", "input", "select", "textarea", "dialog", "table"]
)
def test_raw_form_elements_are_banned(generated, element):
	"""Each has a frappe-ui equivalent; the raw element is how a design system
	quietly stops being one."""
	for app, files in generated.items():
		assert f"'{element}'" in files["frontend/eslint.config.js"], f"{app}: {element}"


def test_apps_pin_the_same_dependency_versions(generated):
	shared = {}
	for app, files in generated.items():
		pkg = json.loads(files["frontend/package.json"])
		for name, version in {**pkg["dependencies"], **pkg["devDependencies"]}.items():
			if name in shared:
				assert shared[name] == version, f"{name} differs between apps"
			shared[name] = version

	# socket.io-client is what the realtime layer needs; frappe-ui alone does not
	# expose a socket.
	assert "socket.io-client" in shared


def test_each_app_serves_its_own_route(generated):
	routes = {app: spec["route"] for app, spec in APPS.items()}
	assert routes["oneapp"] != routes["oneapp_control"], "routes would collide"
	for app, route in routes.items():
		assert f"frontendRoute: '{route}'" in generated[app]["frontend/vite.config.js"]
		# Frappe's desk lives at /app; colliding would shadow it.
		assert not route.startswith("/app")


def test_vite_config_uses_the_frappe_ui_plugin(generated):
	"""The plugin owns the dev proxy, build paths and index.html. Hand-rolling
	any of it is how the two apps drift."""
	for app, files in generated.items():
		assert "frappe-ui/vite" in files["frontend/vite.config.js"], app


def test_tailwind_lists_frappe_ui_content(generated):
	"""Tailwind 3 does not merge `content` from a preset; omitting it purges
	half the component styles."""
	for app, files in generated.items():
		assert "frappeUIContent" in files["frontend/tailwind.config.js"], app


def test_formatter_rules_are_off(generated):
	"""Left on, vue/recommended emits dozens of cosmetic warnings per file and
	trains everyone to ignore lint — which is where the guard rules live."""
	for app, files in generated.items():
		config = files["frontend/eslint.config.js"]
		for rule in (
			"vue/max-attributes-per-line",
			"vue/singleline-html-element-content-newline",
			"vue/html-self-closing",
		):
			assert f"'{rule}': 'off'" in config, f"{app}: {rule} should be off"


def test_banned_elements_carry_a_replacement(generated):
	"""A ban that does not say what to use instead just gets disabled."""
	config = next(iter(generated.values()))["frontend/eslint.config.js"]
	for hint in ("<Button>", "<TextInput>", "<Select>", "<Textarea>", "<Dialog>", "<ListView>"):
		assert hint in config, hint


# --------------------------------------------------------------------------- #
# Component vocabulary
#
# The library has primitives for the things that are easy to hand-roll badly: a
# list, a sidebar item, an icon. Hand-rolled versions look close in isolation and
# wrong next to everything else, so the barrel has to actually offer them.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
	"component",
	[
		# The list family — a <div> stack with divide-y is not a list.
		"List", "ListHeader", "ListHeaderCell", "ListRows", "ListRow", "ListCell",
		# The sidebar family — a <router-link> with an active class is not a
		# sidebar item.
		"Sidebar", "SidebarItem", "SidebarSection", "SidebarLabel", "SidebarHeader",
		# Shell — DesktopShell renders the header target and scroll area itself.
		"DesktopShell", "PageHeader",
		# Icons — frappe-ui resolves `lucide-*` names; inlining SVG was wrong.
		"Icon", "Avatar",
	],
)
def test_barrel_exposes_the_primitive(generated, component):
	for app, files in generated.items():
		assert component in files["frontend/src/ui.js"], f"{app} cannot use <{component}>"


def test_list_family_comes_from_the_list_entry_point(generated):
	"""frappe-ui/list ships its own structural CSS and is a separate entry."""
	for app, files in generated.items():
		assert "from 'frappe-ui/list'" in files["frontend/src/ui.js"], app


def test_the_list_entry_point_is_also_guarded(generated):
	"""Otherwise pages could import list components directly and bypass the
	barrel."""
	for app, files in generated.items():
		assert "frappe-ui/list" in files["frontend/eslint.config.js"], app


def test_barrel_covers_everything_frappe_ui_exports():
	"""A component missing from the barrel is a component someone hand-rolls.

	Skipped when dependencies are not installed, so CI without an npm install
	still runs the rest of the suite.
	"""
	import re

	src = ROOT / "apps/oneapp_control/frontend/node_modules/frappe-ui/src"
	if not src.exists():
		pytest.skip("frappe-ui not installed")

	exported = set()
	index = (src / "index.ts").read_text()
	for target in re.findall(r"export \* from '\./components/([^']+)'", index):
		# Some re-exports name the barrel file explicitly ('Sidebar/index.ts')
		# and some name only the directory ('Rail'). Appending index.ts blindly
		# turned the first kind into .../index.ts/index.ts, which does not exist
		# — so those directories were skipped in silence and their components
		# could go missing from our barrel with this guard still passing.
		candidates = [src / "components" / target]
		candidates += [src / "components" / target / name for name in ("index.ts", "index.js")]
		for path in candidates:
			if path.is_file():
				exported |= set(re.findall(r"export \{ default as (\w+)", path.read_text()))
				break

	barrel = (ROOT / "apps/oneapp_control/frontend/src/ui.js").read_text()
	missing = sorted(c for c in exported if c[0].isupper() and c not in barrel)

	assert not missing, (
		f"{len(missing)} frappe-ui components are not in the barrel and so cannot "
		f"be used: {missing}"
	)


def test_generated_html_shells_are_not_committed():
	"""Every www/*.html the build emits must be gitignored.

	They carry hashed asset filenames. A committed one looks correct in a diff
	and then silently points at assets from an older build — the page loads and
	does nothing, with no error to trace back to the commit that did it.
	"""
	import json
	import re

	gen = (ROOT / "scripts/gen_frontend.py").read_text()
	ignored = (ROOT / ".gitignore").read_text()

	shells = set()
	for app, route in re.findall(r'"(\w+)": \{\s*"route": "/(\w+)"', gen):
		module = "oneapp_control" if app == "oneapp_control" else app
		shells.add(f"apps/{app}/{module}/www/{route}.html")

	# Plus the copies made after the build.
	for app, extra in re.findall(r'"(\w+)": \{[^}]*?"shells": (\[[^\]]*\])', gen, re.S):
		for shell in json.loads(extra):
			shells.add(f"apps/{app}/{app}/www/{shell['name']}.html")

	assert shells, "no shells found — the parse in this guard has stopped working"

	missing = sorted(s for s in shells if s not in ignored)
	assert not missing, f"build output is not gitignored: {missing}"


# --- the app shell ----------------------------------------------------------
#
# DesktopShell and MobileShell are separate components with different slots, so
# something has to choose between them. If each surface chooses for itself, one
# account starts looking like two products on the same tablet — and MobileShell
# has no rail slot at all, so a surface that reaches for it directly silently
# loses app switching on phones.

SHELL = "src/components/AppShell.vue"


def _sources(app: str, suffix: str = ".vue"):
	root = ROOT / f"apps/{app}/frontend/src"
	return {p.relative_to(root.parent).as_posix(): p.read_text() for p in root.rglob(f"*{suffix}")}


@pytest.mark.parametrize("app", ["oneapp", "oneapp_control"])
def test_only_the_shell_composes_the_layout_primitives(app):
	restricted = ("DesktopShell", "MobileShell", "MobileNav", "Rail")
	# The boundary matters: <RailAccount> is a component of ours that happens to
	# start with a restricted name, and matching on the prefix alone would fail
	# this guard on a file that does nothing wrong.
	offenders = {
		path: [name for name in restricted if re.search(rf"<{name}[\s/>]", source)]
		for path, source in _sources(app).items()
		if path != SHELL
	}
	offenders = {k: v for k, v in offenders.items() if v}
	assert not offenders, f"compose <AppShell> instead: {offenders}"


@pytest.mark.parametrize("app", ["oneapp", "oneapp_control"])
def test_shell_is_identical_across_apps(app):
	assert (ROOT / f"apps/{app}/frontend/{SHELL}").read_text() == (
		ROOT / f"apps/oneapp_control/frontend/{SHELL}"
	).read_text()


@pytest.mark.parametrize("app", ["oneapp", "oneapp_control"])
def test_mobile_can_still_reach_the_app_switcher(app):
	# The gap MobileShell leaves: it has no rail slot, so without an explicit
	# switcher a phone user is stuck in whichever app they opened.
	shell = (ROOT / f"apps/{app}/frontend/{SHELL}").read_text()
	assert "BottomSheet" in shell


@pytest.mark.parametrize("app", ["oneapp", "oneapp_control"])
def test_no_binary_theme_toggle(app):
	# A two-state toggle cannot express "follow the system", so appearance is a
	# three-way ThemeSwitcher in settings instead.
	for path, source in _sources(app).items():
		assert "toggleColorScheme" not in source, f"{app}/{path} still toggles the theme"
