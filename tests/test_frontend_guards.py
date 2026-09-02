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
		# Waiting — four shapes for four situations, and a hand-rolled
		# `animate-spin` div is none of them.
		"Spinner", "LoadingIndicator", "LoadingText", "Skeleton",
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

	src = ROOT / "apps/oneapp/frontend/node_modules/frappe-ui/src"
	if not src.exists():
		pytest.skip("frappe-ui not installed")

	exported = set()
	index = (src / "index.ts").read_text()

	# A component frappe-ui has deprecated must stay *out* of the barrel, not in
	# it. ThemeSwitcher is `@deprecated Use Select with useColorScheme instead`
	# and calls warnDeprecated on every render; re-exporting it is how the
	# appearance setting kept using it after 1.0 replaced it.
	deprecated = set()
	for target in re.findall(
		r"/\*\* @deprecated[^*]*\*/\s*export \* from '\./components/([^']+)'", index
	):
		deprecated.add(target.split("/")[0])

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

	# `frappe-ui/charts` is its own entry point, and reading only the main one
	# is how nine chart components stayed invisible to this guard — the barrel
	# could have shipped four of them and the test would have agreed.
	charts = src / "charts" / "index.ts"
	if charts.is_file():
		exported |= set(re.findall(r"export \{ default as (\w+)", charts.read_text()))

	barrel = (ROOT / "apps/oneapp/frontend/src/ui.js").read_text()
	live = {c for c in exported if c[0].isupper()} - deprecated

	missing = sorted(c for c in live if c not in barrel)
	assert not missing, (
		f"{len(missing)} frappe-ui components are not in the barrel and so cannot "
		f"be used: {missing}"
	)

	stale = sorted(c for c in deprecated if c in barrel)
	assert not stale, (
		f"frappe-ui deprecated {stale}; drop them from the barrel and use the "
		f"replacement its index.ts names"
	)


def test_the_deprecation_reader_still_finds_one():
	"""If the marker moves, the rule above passes by finding nothing to enforce."""
	import re

	src = ROOT / "apps/oneapp/frontend/node_modules/frappe-ui/src"
	if not src.exists():
		pytest.skip("frappe-ui not installed")

	index = (src / "index.ts").read_text()
	assert re.search(r"/\*\* @deprecated[^*]*\*/\s*export \* from", index), (
		"no @deprecated export found in frappe-ui's index.ts — either the "
		"package stopped marking them this way, or the pattern needs updating"
	)


def test_generated_html_shells_are_not_committed():
	"""Every www/*.html the build emits must be gitignored.

	They carry hashed asset filenames. A committed one looks correct in a diff
	and then silently points at assets from an older build — the page loads and
	does nothing, with no error to trace back to the commit that did it.
	"""
	import importlib.util

	# The generator is imported rather than parsed. Reading its source with a
	# regex and json.loads worked until a constant appeared inside the literal,
	# at which point the guard failed on its own parsing rather than on anything
	# real.
	spec = importlib.util.spec_from_file_location("gen_frontend", ROOT / "scripts/gen_frontend.py")
	gen = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(gen)

	ignored = (ROOT / ".gitignore").read_text()

	shells = set()
	for app, config in gen.APPS.items():
		route = config["route"].lstrip("/")
		shells.add(f"apps/{app}/{app}/www/{route}.html")
		for extra in config.get("shells", []):
			shells.add(f"apps/{app}/{app}/www/{extra['name']}.html")

	assert shells, "no shells found — the generator's shape has changed"

	missing = sorted(s for s in shells if s not in ignored)
	assert not missing, f"build output is not gitignored: {missing}"


@pytest.mark.parametrize("app", ["oneapp", "oneapp_control"])
def test_listrows_is_given_items(app):
    """<ListRows> iterates its `items` prop; a v-for child renders nothing.

    This is the worst shape of frontend bug: the page loads, the count beside
    the heading is right because it comes from the same array, and the list is
    simply empty. Eight pages shipped like this — every list in the admin
    console and the customer portal — before anyone opened one on a phone.
    """
    for path, source in _sources(app).items():
        for match in re.finditer(r"<ListRows\b([^>]*)>", source):
            attrs = match.group(1)
            assert ":items" in attrs or "v-bind" in attrs, (
                f"{app}/{path}: <ListRows> without :items renders no rows"
            )
            assert "v-slot" in attrs or "#default" in attrs, (
                f"{app}/{path}: <ListRows> needs a scoped slot to render each item"
            )


# --- the app shell ----------------------------------------------------------
#
# DesktopShell and MobileShell are separate components with different slots, so
# something has to choose between them. If each surface chooses for itself, one
# account starts looking like two products on the same tablet — and MobileShell
# has no rail slot at all, so a surface that reaches for it directly silently
# loses app switching on phones.

SHELL = "src/components/AppShell.vue"

# Which bundles render the shell at all. `oneapp_control` is a signup page and
# nothing else now — no rail, no bottom bar, no account menu — so asking it to
# have one would only teach us to generate an AppShell no route mounts. It is
# read off the generator's own spec rather than off the filesystem: a bundle
# stops having a shell by someone deleting `shell: True`, which is a visible
# act, not by a file quietly going missing.
SHELL_APPS = tuple(app for app, spec in APPS.items() if spec.get("shell"))


def _sources(app: str, suffix: str = ".vue"):
	root = ROOT / f"apps/{app}/frontend/src"
	return {p.relative_to(root.parent).as_posix(): p.read_text() for p in root.rglob(f"*{suffix}")}


@pytest.mark.parametrize("app", APPS)
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


def test_the_shell_is_generated_rather_than_written():
	"""It used to be two apps holding byte-identical copies; that is what this
	compared. One bundle renders a shell now, so what is left to check is the
	other half of the same claim — that nobody edits the copy on disk instead of
	the template it comes from, which is how the two used to drift apart.
	"""
	from gen_frontend import APP_SHELL_VUE

	for app in SHELL_APPS:
		assert (ROOT / f"apps/{app}/frontend/{SHELL}").read_text() == APP_SHELL_VUE, (
			f"{app}'s shell was edited in place — edit scripts/gen_frontend.py"
		)


@pytest.mark.parametrize("app", SHELL_APPS)
def test_mobile_can_still_reach_the_app_switcher(app):
	# The gap MobileShell leaves: it has no rail slot, so without an explicit
	# switcher a phone user is stuck in whichever app they opened.
	shell = (ROOT / f"apps/{app}/frontend/{SHELL}").read_text()
	assert "BottomSheet" in shell


@pytest.mark.parametrize("app", APPS)
def test_no_binary_theme_toggle(app):
	# A two-state toggle cannot express "follow the system", so appearance is a
	# three-way ThemeSwitcher in settings instead.
	for path, source in _sources(app).items():
		assert "toggleColorScheme" not in source, f"{app}/{path} still toggles the theme"


# --------------------------------------------------------------------------- #
# Not hand-rolling what the library ships
#
# The rule the user set: if frappe-ui has a component, we use it. These make
# that checkable rather than a matter of remembering.
# --------------------------------------------------------------------------- #

def _local_components():
	"""Every .vue file we wrote, by app."""
	found = {}
	for app in APPS:
		root = ROOT / f"apps/{app}/frontend/src"
		found[app] = sorted(root.rglob("*.vue"))
	return found


def _barrel_names():
	barrel = (ROOT / "apps/oneapp/frontend/src/ui.js").read_text()
	import re

	return set(re.findall(r"^\s{2}([A-Z]\w+),", barrel, re.M))


def test_no_local_component_shadows_a_frappe_ui_one():
	"""A local `Badge.vue` beside the barrel's `Badge` is a coin toss per file.

	Only exact names are checked. `SpaceSidebar` and `PortalSidebar` are
	compositions *of* `Sidebar`, which is the point — it is the file that
	replaces a primitive outright that this is looking for.
	"""
	names = _barrel_names()
	assert len(names) > 60, f"only read {len(names)} names from the barrel"

	clashes = []
	for app, paths in _local_components().items():
		for path in paths:
			if path.stem in names:
				clashes.append(f"{app}/{path.name} shadows frappe-ui's <{path.stem}>")
	assert not clashes, "\n".join(clashes)


# The one kind of file this cannot ask for: layout with no widget in it.
#
# RecordPane is a drag handle and a box that gets wider. frappe-ui ships no
# resizer and no split pane — the component list was read, not assumed — so
# there is nothing to compose it out of, and the alternative was importing
# something it does not use to satisfy a test. Named one at a time on purpose:
# the next file like it has to argue its case here rather than slip through.
# `Resizer.vue` for the same reason: it is a hit area and a rule. The barrel
# has no drag handle to compose it out of, and everything it does — the floor,
# the ceiling, the keyboard, the width remembered per browser — is behaviour
# rather than markup.
# `FadedScroll.vue` is the third: a scroll box and two gradients. There is no
# scroller in the barrel that fades its own edges, and what it does — measuring
# whether there is content past each edge — is behaviour rather than markup.
LAYOUT_ONLY = frozenset({"RecordPane.vue", "Resizer.vue", "FadedScroll.vue"})


def test_local_components_compose_the_vocabulary():
	"""A component that imports nothing is markup wearing a component's name.

	Every one of ours has to be built out of the barrel, or out of another of
	ours that is. The tenant app's 404 page was the exception: a hand-built
	centred div with a `text-blue-600` router-link, which is both a hand-rolled
	EmptyState and a colour that does not follow the theme.
	"""
	raw = []
	for app, paths in _local_components().items():
		for path in paths:
			source = path.read_text()
			if path.name in LAYOUT_ONLY:
				continue
			if "from '@/ui'" in source:
				continue
			# Composing our own components is fine — they bottom out in the barrel.
			if re.search(r"import \w+ from '[^']*\.vue'", source):
				continue
			raw.append(f"{app}/{path.relative_to(ROOT / f'apps/{app}/frontend/src')}")
	assert not raw, (
		"these build their markup from scratch instead of from the barrel: "
		+ ", ".join(raw)
	)


# Tailwind's own palette is not the design system. `text-blue-600` is a fixed
# colour: it does not move with the theme, so it stays a light-mode blue on a
# dark background. frappe-ui's semantic tokens — ink / surface / outline — are
# what the theme actually redefines.
PALETTE = (
	"slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|"
	"teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose"
)


def test_colours_come_from_semantic_tokens():
	offenders = []
	pattern = re.compile(rf"\b(?:text|bg|border|ring|divide)-(?:{PALETTE})-\d{{2,3}}\b")
	for app, paths in _local_components().items():
		for path in paths:
			for match in set(pattern.findall(path.read_text())):
				offenders.append(f"{app}/{path.name}: {match}")
	assert not offenders, (
		"raw Tailwind palette colours do not follow the theme; use the ink / "
		"surface / outline tokens instead: " + ", ".join(sorted(offenders))
	)


def test_the_prepaint_theme_script_matches_the_composable():
	"""The scheme is applied from JS on load, so a shell without `data-theme`
	shows the default and then switches — a visible flash on every cold load.

	Each shell sets the attribute before the app script runs. That only works
	while it reads the key `useColorScheme` writes, and sets the attribute it
	reads, so both are checked against the composable rather than assumed.
	"""
	src = ROOT / "apps/oneapp/frontend/node_modules/frappe-ui/src"
	if not src.exists():
		pytest.skip("frappe-ui not installed")

	composable = (src / "composables/useColorScheme.ts").read_text()
	key = re.search(r"STORAGE_KEY\s*=\s*'([^']+)'", composable)
	attribute = re.search(r"DOM_ATTRIBUTE\s*=\s*'([^']+)'", composable)
	assert key and attribute, "useColorScheme no longer names its key/attribute"

	# One authored shell per bundle, plus whatever www copies are checked in.
	# The rest are emitted by the build from these, so a copy cannot disagree.
	shells = sorted(ROOT.glob("apps/*/frontend/index.html")) + sorted(
		ROOT.glob("apps/*/*/www/*.html")
	)
	authored = {path for path in shells if path.name == "index.html"}
	assert len(authored) == len(APPS), (
		f"found {len(authored)} authored shells for {len(APPS)} bundles"
	)
	assert len(shells) > len(authored), "no www shell is checked in any more"
	for shell in shells:
		html = shell.read_text()
		assert f"localStorage.getItem('{key.group(1)}')" in html, (
			f"{shell.name} reads a different key than useColorScheme writes"
		)
		assert f"setAttribute('{attribute.group(1)}'" in html, (
			f"{shell.name} sets a different attribute than useColorScheme reads"
		)
		# Before the module script, or it is not a pre-paint script at all.
		assert html.index("setAttribute") < html.index("<body"), (
			f"{shell.name} sets the theme after the body starts"
		)


def test_stored_datetimes_are_converted_from_the_site_timezone():
	"""Frappe writes datetimes in the site's timezone, not the reader's.

	`dayjs(value)` reads a stored timestamp as if it were already local, which
	puts an invoice on the wrong day for anyone far enough from the server.
	`dayjsLocal` does the conversion — but only once `systemTimezone` is
	configured, so the boot payload has to carry it and main.js has to set it.
	"""
	for app in APPS:
		root = ROOT / f"apps/{app}/frontend/src"

		boot = (root / "lib/boot.js").read_text()
		assert "system_timezone" in boot, f"{app}: boot.js does not read the timezone"

		main = (root / "main.js").read_text()
		assert "setConfig('systemTimezone'" in main, f"{app}: main.js never configures it"

		for path in sorted(root.rglob("*.vue")):
			source = path.read_text()
			bare = re.findall(r"(?<![\w.])dayjs\(", source)
			assert not bare, (
				f"{app}/{path.name} formats a stored datetime with dayjs(); "
				f"use dayjsLocal so it converts from the site timezone"
			)

	for controller in sorted(ROOT.glob("apps/*/*/www/*.py")):
		if controller.name == "__init__.py":
			continue
		assert "system_timezone" in controller.read_text(), (
			f"{controller.name} does not put the system timezone in its boot context"
		)


def test_the_installed_frappe_ui_matches_the_pin():
	"""Every API guard reads the *installed* package.

	Prop and slot declarations, literal unions, retired tokens, the settings
	dialog's geometry — all of it comes out of node_modules. If node_modules is
	behind the pin, those guards validate the code against a version that is not
	the one being shipped, and pass while the built app is wrong. This is the
	guard the other guards rest on.
	"""
	pins, installs = {}, {}
	for app in APPS:
		pkg = json.loads((ROOT / f"apps/{app}/frontend/package.json").read_text())
		pins[app] = pkg["dependencies"]["frappe-ui"]

		installed = ROOT / f"apps/{app}/frontend/node_modules/frappe-ui/package.json"
		if not installed.exists():
			pytest.skip(f"{app}: frappe-ui not installed")
		installs[app] = json.loads(installed.read_text())["version"]

	assert len(set(pins.values())) == 1, f"the apps pin different versions: {pins}"
	assert len(set(installs.values())) == 1, f"the apps installed different versions: {installs}"

	pin = next(iter(pins.values())).lstrip("^~")
	version = next(iter(installs.values()))
	assert version == pin, (
		f"pinned {pin} but installed {version} — the API guards are reading "
		f"{version}'s declarations while the app ships against {pin}"
	)


def test_we_are_on_the_v1_line():
	"""npm's `latest` tag still points at v0, so a bare install lands there.

	Every rule in these guards — flat Dialog props, `theme` over `variant`, the
	numbered radius scale, the document layer — is v1. On v0 they would be
	checking the wrong library entirely.
	"""
	for app in APPS:
		pkg = json.loads((ROOT / f"apps/{app}/frontend/package.json").read_text())
		assert pkg["dependencies"]["frappe-ui"].lstrip("^~").startswith("1."), (
			f"{app} is not pinned to the v1 line"
		)


# --------------------------------------------------------------------------- #
# Navigation is declared once
#
# The sidebar and the phone's bottom bar are two renderings of one list. Declared
# separately they drift, and they did: the same page was "Readiness" with a
# checklist icon in the sidebar and "Setup" with a gear in the bottom bar, which
# reads as two different features — and put a second gear next to the settings
# dialog's.
# --------------------------------------------------------------------------- #

NAV_MODULE = "lib/nav.js"
def _declares_a_nav_item(source: str) -> bool:
	"""Does this file contain an object literal with both an icon and a route?

	The innermost enclosing literal, found by walking the braces, rather than a
	regex: the destination is itself an object (`to: { name, params: {...} }`),
	so a fixed nesting depth either misses real entries or matches the whole
	surrounding array.
	"""
	for match in re.finditer(r"\bicon:", source):
		start, depth = None, 0
		for i in range(match.start() - 1, -1, -1):
			if source[i] == "}":
				depth += 1
			elif source[i] == "{":
				if depth == 0:
					start = i
					break
				depth -= 1
		if start is None:
			continue
		depth = 0
		for j in range(start, len(source)):
			if source[j] == "{":
				depth += 1
			elif source[j] == "}":
				depth -= 1
				if depth == 0:
					break
		else:
			continue
		if re.search(r"\bto:", source[start : j + 1]):
			return True
	return False


@pytest.mark.parametrize("app", SHELL_APPS)
def test_navigation_is_declared_in_one_place(app):
	root = ROOT / f"apps/{app}/frontend/src"
	assert (root / NAV_MODULE).exists(), f"{app} has no {NAV_MODULE}"

	offenders = []
	for path in sorted(root.rglob("*")):
		if path.suffix not in (".vue", ".js"):
			continue
		if path.relative_to(root).as_posix() == NAV_MODULE:
			continue
		if _declares_a_nav_item(path.read_text()):
			offenders.append(path.relative_to(root).as_posix())
	assert not offenders, (
		f"navigation entries declared outside {NAV_MODULE}: {offenders} — the "
		f"sidebar and the bottom bar have to render the same list"
	)


@pytest.mark.parametrize("app", SHELL_APPS)
def test_both_renderings_read_that_one_list(app):
	"""Not merely that the module exists — that nothing bypasses it."""
	root = ROOT / f"apps/{app}/frontend/src"
	shell_consumer = (root / "App.vue").read_text()
	assert "useNav" in shell_consumer, f"{app}/App.vue does not feed AppShell from {NAV_MODULE}"

	sidebars = [p for p in root.rglob("*Sidebar.vue")]
	assert sidebars, f"{app} has no sidebar"
	for path in sidebars:
		assert "useNav" in path.read_text(), f"{path.name} declares its own navigation"


def test_the_bottom_bar_leaves_a_slot_for_everything_else():
	"""A grid bar of equal columns stops being readable past five on a phone,
	and a sidebar can hold twenty entries. The last slot is always the account,
	opening a sheet, so nothing a surface declares is unreachable."""
	shell = (ROOT / f"apps/{SHELL_APPS[0]}/frontend/{SHELL}").read_text()

	assert "PRIMARY_SLOTS = 4" in shell, "the bar no longer reserves a slot for More"
	assert "slice(0, PRIMARY_SLOTS)" in shell, "the bar is no longer capped"
	assert 'label="More"' in shell, "there is no way into the sheet"
	# Everything the desktop keeps in the rail, its footer and the sidebar foot.
	#
	# `navItems` and not `overflowNav`: the sheet lists every destination this
	# surface has, not only the ones the bar had no room for. A list that
	# silently omits the four you can already see is a list you cannot trust to
	# be complete — and it went empty on a space whose screens all fit.
	for reachable in ("navItems", "entryOptions", "menuItems", "iconOptions", "logout"):
		assert reachable in shell, f"the More sheet cannot reach {reachable}"


@pytest.mark.parametrize("app", SHELL_APPS)
def test_appearance_is_reachable_without_opening_settings(app):
	"""It is the preference people change most often; behind a dialog is the
	slow path. Three options, not a toggle — see test_no_binary_theme_toggle."""
	root = ROOT / f"apps/{app}/frontend/src"
	assert (root / "lib/appearance.js").exists(), f"{app} has no appearance module"

	# The account menu, wherever this surface puts it, and the phone's sheet.
	menus = [p for p in root.rglob("*.vue") if "Dropdown" in p.read_text() and "Avatar" in p.read_text()]
	assert menus, f"{app} has no account menu"
	assert any("useAppearance" in p.read_text() for p in menus), (
		f"{app}: no account menu offers appearance"
	)
	assert "useAppearance" in (root / "components/AppShell.vue").read_text()


# --------------------------------------------------------------------------- #
# Lists fit the screen they are on
#
# frappe-ui's List takes explicit grid tracks. Fixed rem tracks add up, and a
# 390px phone has about 20rem of row to spend: three desktop-sized columns left
# roughly 60px for the identity column, so the workspace name — the one thing
# the row exists to say — truncated to "W…" while a plan code kept its full
# width.
# --------------------------------------------------------------------------- #

# 390px screen − page padding − row padding ≈ 20rem, and the identity column
# needs about 9rem of that to be worth reading.
PHONE_FIXED_TRACK_BUDGET = 11.0

# Scoped to `<List>` itself. A settings catalogue passes its tracks to
# CatalogueList, which puts them inside a horizontal scroller on purpose — a
# table someone is reading keeps every column and takes a scrollbar, rather
# than dropping one.
COLUMNS_BINDING = re.compile(r'<List\s[^>]*?:columns="(\[[^"]*\])"', re.S)


def _fixed_rems(tracks: str) -> float:
	return sum(float(v) for v in re.findall(r"'([\d.]+)rem'", tracks))


@pytest.mark.parametrize("app", APPS)
def test_lists_wider_than_a_phone_declare_what_they_drop(app):
	root = ROOT / f"apps/{app}/frontend/src"
	offenders = []
	for path in sorted(root.rglob("*.vue")):
		rel = path.relative_to(root).as_posix()
		for tracks in COLUMNS_BINDING.findall(path.read_text()):
			total = _fixed_rems(tracks)
			if total > PHONE_FIXED_TRACK_BUDGET:
				offenders.append(f"{rel}: {tracks} = {total}rem of fixed tracks")
	assert not offenders, (
		"these lists spend more than "
		f"{PHONE_FIXED_TRACK_BUDGET}rem on fixed columns, which is more than a "
		"phone has after the identity column. Declare them through "
		"useListColumns and say which columns a phone can spare:\n"
		+ "\n".join(offenders)
	)


@pytest.mark.parametrize("app", APPS)
def test_a_dropped_column_takes_its_cell_with_it(app):
	"""Tracks and cells have to agree about how many columns there are.

	A cell left rendering after its track is gone shifts every cell in the row
	one place left — which looks like the data is wrong rather than the layout.
	"""
	root = ROOT / f"apps/{app}/frontend/src"
	offenders = []
	for path in sorted(root.rglob("*.vue")):
		source = path.read_text()
		dropped = re.findall(r"\{\s*key:\s*'([^']+)'[^}]*mobile:\s*false", source)
		for key in dropped:
			# `shows(...)` or a renamed destructure of it — a file with several
			# lists needs `domainShows`, `backupShows` and so on.
			assert re.search(rf"[Ss]hows\('{re.escape(key)}'\)", source), (
				f"{path.relative_to(root)}: column '{key}' is dropped on a phone "
				f"but no cell tests shows('{key}')"
			)
		# The converse: a `shows()` for a key that is never declared silently
		# renders nothing at every width.
		for key in set(re.findall(r"[Ss]hows\('([^']+)'\)", source)):
			if f"key: '{key}'" not in source:
				offenders.append(f"{path.relative_to(root)}: shows('{key}') is not a column")
	assert not offenders, "; ".join(offenders)


def _column_helper_results(source: str) -> list[str]:
	"""Names a `useListColumns(...)` result is bound to, when not destructured."""
	return re.findall(r"const\s+(\w+)\s*=\s*useListColumns\(", source)


@pytest.mark.parametrize("app", APPS)
def test_a_column_set_is_destructured_not_held_as_an_object(app):
	"""Vue unwraps a ref bound at the top level of `setup`, not one reached
	through a property.

	`const list = useListColumns(...)` then `:columns="list.columns"` hands List
	a ComputedRef, and it fails at `columns.join` with a message that names
	neither the list nor the ref — which is exactly how the tenant page's
	Domains, Backups and Activity tabs shipped broken. Destructuring is the only
	spelling that works, so it is the only one allowed.
	"""
	root = ROOT / f"apps/{app}/frontend/src"
	offenders = []
	for path in sorted(root.rglob("*.vue")):
		held = _column_helper_results(path.read_text())
		if held:
			offenders.append(f"{path.relative_to(root)}: {held}")
	assert not offenders, (
		"destructure the result — `const { visible, columns, shows } = "
		"useListColumns(...)`: " + "; ".join(offenders)
	)


@pytest.mark.parametrize("app", APPS)
def test_no_computed_ref_is_bound_straight_into_a_template(app):
	"""The same mistake in general: `:prop="obj.something"` where `something` is
	a ref on a plain object.

	Only the shape this project has actually been bitten by is checked — a
	binding whose value is a property of a `useListColumns` result — because a
	general "is this a ref" check needs a type system we do not have here.
	"""
	root = ROOT / f"apps/{app}/frontend/src"
	offenders = []
	for path in sorted(root.rglob("*.vue")):
		source = path.read_text()
		names = re.findall(r"const\s+(\w+)\s*=\s*useListColumns\(", source)
		for name in names:
			for match in re.findall(rf'"{name}\.(\w+)"', source):
				offenders.append(f"{path.relative_to(root)}: {name}.{match}")
	assert not offenders, "these bind a ref, not its value: " + "; ".join(offenders)


# --------------------------------------------------------------------------- #
# Waiting
#
# frappe-ui ships four ways to say "not yet": Skeleton for something whose shape
# is already known, LoadingIndicator and Spinner for a wait with no shape, and
# LoadingText for a wait worth naming. A hand-rolled `animate-spin` div is a
# fifth that matches none of them, and the mismatch is what a customer sees:
# every list on the site pulsing differently while it loads.
# --------------------------------------------------------------------------- #

SPINNER = re.compile(r"animate-spin|animate-pulse|border-t-transparent")


@pytest.mark.parametrize("app", APPS)
def test_no_hand_rolled_spinner(app):
	root = ROOT / f"apps/{app}/frontend/src"
	offenders = [
		str(path.relative_to(root))
		for path in sorted(root.rglob("*.vue"))
		if SPINNER.search(path.read_text())
	]
	assert not offenders, (
		"use Skeleton / LoadingIndicator / LoadingText / Spinner from @/ui "
		"rather than a hand-rolled one: " + ", ".join(offenders)
	)


# A `<Button>` tag, whole, so its attributes can be read together.
BUTTON = re.compile(r"<Button\b[^>]*?/?>", re.S)
# `icon="lucide-x"` or `:icon="…"`, and not `icon-left` / `icon-right`, which
# sit beside a label rather than instead of one.
ICON_ONLY = re.compile(r'(?<![\w-])(:?)icon="([^"]*)"')
HAS_TOOLTIP = re.compile(r'(?<![\w-]):?tooltip="')


@pytest.mark.parametrize("app", APPS)
def test_an_icon_only_control_says_what_it_does(app):
	"""A button that is only a picture has to name itself on hover.

	`label` on an icon-only Button is the *accessible* name — it reaches a
	screen reader and nobody else. The gear beside a list, the two pin arrows in
	the column picker, the heart: sighted people were left to guess, and half of
	them are one click from changing what a list shows.

	frappe-ui's Button takes a `tooltip`, which builds its own Tooltip
	internally — so this is also what keeps every tooltip in both SPAs the same
	component.

	Exempt is the button that is *sometimes* an icon:
	`:icon="isMobile ? 'lucide-pencil' : undefined"` shows its label wherever
	there is a pointer to hover with, and a tooltip on a touch screen is one
	nobody can open. A ternary choosing between two icons is not that — it is
	always an icon — so `undefined` in the expression is the test, not `?`.
	"""
	root = ROOT / f"apps/{app}/frontend/src"
	offenders = []
	for path in sorted(root.rglob("*.vue")):
		source = path.read_text()
		for match in BUTTON.finditer(source):
			tag = match.group(0)
			icon = ICON_ONLY.search(tag)
			if not icon or "undefined" in icon.group(2):
				continue
			if HAS_TOOLTIP.search(tag):
				continue
			line = source[: match.start()].count("\n") + 1
			offenders.append(f"{path.relative_to(root)}:{line}")
	assert not offenders, (
		"these render as an icon and nothing else, with no tooltip to say what "
		"they do: " + ", ".join(offenders)
	)


@pytest.mark.parametrize("app", APPS)
def test_a_tooltip_is_frappe_uis_or_it_is_not_a_tooltip(app):
	"""One component, or four things that behave differently on a phone.

	The browser's own `title` is the tempting shortcut and it is not a tooltip:
	it appears after a delay nobody controls, cannot be styled, cannot hold
	markup, and does nothing at all on a touch screen. A hand-rolled hover card
	— `@mouseenter` flipping a ref, a `group-hover` absolute div — is the other
	way this drifts, and it arrives without the delay, the dismissal or the
	portal that frappe-ui's already handles.

	`title` on a *component* is left alone: it is a real prop on Alert, Dialog,
	EmptyState and SettingsRow, and means the heading rather than a hover.

	And on an `<iframe>`, where it is not a hover either: a frame's `title` is
	its accessible name — the only one it can have — and a screen reader reads
	the frame by it. Leaving it off to satisfy this rule would trade a tooltip
	nobody sees for a document nobody can find.
	"""
	root = ROOT / f"apps/{app}/frontend/src"
	html_title = re.compile(r"<(?!iframe\b)[a-z][\w-]*\s[^>]*?\stitle=", re.S)
	hover = re.compile(r"@mouse(enter|over|leave)|group-hover:")
	offenders = []
	for path in sorted(root.rglob("*.vue")):
		source = path.read_text()
		if html_title.search(source) or hover.search(source):
			offenders.append(str(path.relative_to(root)))
	assert not offenders, (
		"use frappe-ui's Tooltip (or Button's own `tooltip`) rather than a "
		"`title` attribute or a hand-rolled hover: " + ", ".join(offenders)
	)


@pytest.mark.parametrize("app", APPS)
def test_something_waits_visibly_while_a_screen_loads(app):
	"""A screen that fetches and renders nothing in the meantime reads as broken
	rather than as slow. Whatever tracks a `loading` ref has to show it — and
	most of them are panels under components/, not pages.

	Handing the ref to a component's own `loading` prop counts: Combobox
	replaces its results with a wait, and Button draws a spinner in place of its
	label. Both are the component's answer to this question, and a Skeleton
	stapled beside one would be a second wait for the same fetch.
	"""
	root = ROOT / f"apps/{app}/frontend/src"
	waiting = re.compile(
		r"<(Skeleton|LoadingIndicator|LoadingText|Spinner)\b|:loading="
	)
	offenders = []
	for path in sorted(root.rglob("*.vue")):
		source = path.read_text()
		if re.search(r"const (loading|\w*Loading) = ref\(", source) and not waiting.search(source):
			offenders.append(str(path.relative_to(root)))
	assert not offenders, (
		"these track a loading state and render nothing while it is true: "
		+ ", ".join(offenders)
	)


# --------------------------------------------------------------------------- #
# One screen means one thing on every screen
#
# A saved view is a person's answer to "what do I look at". A phone that
# silently drops half of it is answering a different question — and once the
# columns are the reader's own choice, there is nothing left to guess on their
# behalf. The table scrolls sideways instead, which is what Frappe CRM does.
#
# This is the screen host only. A hand-authored panel in the console has neither a
# reader-chosen column set nor a horizontal scroller, so `useListColumns` and
# its `mobile:` key are still how those narrow.
# --------------------------------------------------------------------------- #

SCREEN_HOST = ROOT / "apps/oneapp/frontend/src/pages/ScreenHost.vue"
# The shell renders a body per view type; the list is the one that draws a grid.
LIST_BODY = ROOT / "apps/oneapp/frontend/src/components/screen/ListBody.vue"
RECORD_TABLE = ROOT / "apps/oneapp/frontend/src/components/screen/RecordTable.vue"
CHILD_TABLE = ROOT / "apps/oneapp/frontend/src/components/screen/ChildTable.vue"


def test_the_screen_host_shows_the_same_columns_on_every_screen():
	source = SCREEN_HOST.read_text() + LIST_BODY.read_text()
	offenders = []
	if "useListColumns" in source.replace("`useListColumns`", ""):
		offenders.append("it calls useListColumns, which exists to narrow a list for a phone")
	if re.search(r"^\s*mobile:", source, re.M):
		offenders.append("a column declares a `mobile:` behaviour")
	if "useIsMobile" in source:
		offenders.append("it asks the viewport, which the column set must not depend on")
	assert not offenders, (
		"ScreenHost.vue must render one column set at every width:\n  "
		+ "\n  ".join(offenders)
	)


# --------------------------------------------------------------------------- #
# A header band replaces the header's own rule
#
# frappe-ui draws `ListHeader`'s bottom border as a grid child inset to the
# content box, so it lines up with the rows' dividers. Fill the header and that
# rule stops short at both ends of the fill — which is exactly the "weird
# border below the band" it rendered as. Whoever adds the fill owns the rule.
# --------------------------------------------------------------------------- #

BAND = "[data-slot=list-header]]:bg-"
OWN_RULE = "[data-slot=list-header-border]]:hidden"


@pytest.mark.parametrize("app", APPS)
def test_a_filled_list_header_hides_the_rule_it_covers(app):
	root = ROOT / f"apps/{app}/frontend/src"
	offenders = []
	for path in sorted(root.rglob("*.vue")):
		source = path.read_text()
		if BAND in source and OWN_RULE not in source:
			offenders.append(str(path.relative_to(root)))
	assert not offenders, (
		"these fill the list header without hiding its own inset rule, which "
		f"then stops short at both ends of the fill — add `{OWN_RULE}` and draw "
		"a full-width border on the header instead: " + ", ".join(offenders)
	)


# --------------------------------------------------------------------------- #
# A pane is two halves
#
# The list is a fixed-height grid so its horizontal scrollbar lands at the
# bottom of the window rather than at the bottom of the table. That needs the
# shell's own page scrolling off for the route — and the two halves live in
# different files, so either one can go without the other and the failure is
# quiet: with only the route flag the pane has no height to fill; with only the
# shell change the page stops scrolling for screens that need it.
# --------------------------------------------------------------------------- #

def test_the_screen_host_is_a_pane_at_both_ends():
	root = ROOT / "apps/oneapp/frontend/src"
	router = (root / "router.js").read_text()
	app = (root / "App.vue").read_text()

	assert re.search(r"ScreenHost\.vue'\),[\s\S]{0,900}?meta:\s*\{[^}]*pane:\s*true", router), (
		"router.js no longer marks the screen host's route as a pane"
	)
	assert 'scroll="!$route.meta.pane"' in app, (
		"App.vue no longer turns the shell's page scroll off for a pane route"
	)


BOARD_BODY = ROOT / "apps/oneapp/frontend/src/components/screen/BoardBody.vue"
CARDS_BODY = ROOT / "apps/oneapp/frontend/src/components/screen/CardsBody.vue"
CARDS_LIB = ROOT / "apps/oneapp/frontend/src/lib/cards.js"


def test_a_card_is_mapped_in_one_place():
	"""The board and the grid draw one card, from one mapping.

	The same lesson the table taught twice: chrome written once and copied into
	the second caller drifts, quietly, and the drift shows up as one surface
	being subtly wrong for months. What a card says has real rules in it — which
	field is the title, that a blank field is left off entirely, that the cap
	comes after the blanks are dropped — and a second copy of those rules is a
	second set of answers to the same question.

	The arrangement is deliberately not shared: a board buckets its cards and
	lets you drag one between buckets, a grid lays them out flat. That is what
	the two files are for.
	"""
	for path in (BOARD_BODY, CARDS_BODY):
		source = re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.S)
		assert "lib/cards" in source, (
			f"{path.name} no longer draws its card with the shared mapping"
		)
		for own in ("cardIdentity", "cardShown", "cardValues"):
			assert f"const {own} =" not in source and f"function {own}" not in source, (
				f"{path.name} defines its own {own} — one card, one mapping"
			)
		assert "RecordCard" in source, (
			f"{path.name} no longer renders RecordCard, which is the card itself"
		)
		# The card's meta band ends in a real `<button>` — the heart — so the
		# tile around it cannot be one. It was, in the grid, for exactly as long
		# as the card had nothing pressable on it. Lowercase, because the
		# frappe-ui component is `<Button>` and a column heading may hold one.
		assert "<button" not in source, (
			f"{path.name} wraps its cards in a raw <button>; the card has "
			"controls of its own, and a button inside a button is not something "
			"a browser renders. The tile is a click surface and the title "
			"inside it is the keyboard target — see RecordCard."
		)

	# And the mapping knows nothing about how the cards are laid out. A `bucket`
	# or a `drag` in here is the board leaking into the thing the grid shares.
	# (`column` is not one of these: the reader's list columns are where a card
	# gets its fields from when nobody has chosen any.)
	lib = re.sub(r"/\*.*?\*/|//[^\n]*", "", CARDS_LIB.read_text(), flags=re.S)
	for arrangement in ("bucket", "drag", "board", "grid"):
		assert arrangement not in lib.lower(), (
			f"lib/cards.js mentions `{arrangement}` outside its comments — the "
			"card is what a record says, not where it is put"
		)


def test_the_table_has_exactly_one_scroller():
	"""Both axes on one element, or the header drifts.

	A separate horizontal wrapper around a vertical one is the obvious way to
	build this and it is wrong: the header then sits outside the vertical
	scrollbar's gutter and is a scrollbar's width out of true with the rows
	under it. One element scrolling both ways has no gutter to disagree about.

	One element, and one *place*: `RecordTable` owns the scroller for both the
	list and the child grid, so this is the only file that may have one. A body
	that grows its own is a body that has started rebuilding the table.
	"""
	table = RECORD_TABLE.read_text()
	assert table.count('ref="scroller"') == 1, "the table should have one scroller"
	# Both classes appear once, in that element's own binding: `overflow-auto`
	# where the table fills a pane, `overflow-x-auto` where it is as tall as its
	# rows and only ever runs out of width.
	assert table.count("overflow-auto") == 1
	assert table.count("overflow-x-auto") == 1

	# And the bodies delegate rather than wrapping it in one of their own.
	for path in (LIST_BODY, CHILD_TABLE):
		source = re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.S)
		assert "RecordTable" in source, (
			f"{path.name} no longer draws itself with the shared table — the "
			"chrome was written twice before and drifted both times"
		)
		assert "overflow-" not in source, (
			f"{path.name} scrolls something itself — the table owns the scroller, "
			"and a second one around it is the shape that drifts"
		)

	# The shell scrolls nothing itself. `overflow-y-auto` appears once: the
	# escape hatch a screen a space wrote itself renders into, which cannot be
	# assumed to fit a pane.
	shell = SCREEN_HOST.read_text()
	assert shell.count("overflow-y-auto") == 1
	assert "overflow-auto" not in shell


def test_no_component_is_shadowed_by_a_copy_in_a_screen():
	"""One component, one behaviour.

	`screens/account/` carried its own `UsageBar.vue`, identical to the one in
	`components/` that the generator owns. Editing the generated one changed
	nothing on the account screen, and nothing in either file said the other
	existed — the two just rendered differently.

	A screen may of course have components of its own. What it may not have is
	one whose name is already taken in `components/`.
	"""
	offenders = []

	for app in APPS:
		frontend = ROOT / "apps" / app / "frontend"
		shared = {p.name for p in (frontend / "src/components").glob("*.vue")}
		for path in (frontend / "src/screens").rglob("*.vue"):
			if path.name in shared:
				offenders.append(path.relative_to(frontend).as_posix())

	assert not offenders, (
		"these shadow a component of the same name in components/: "
		+ ", ".join(sorted(offenders))
	)


# A `<TabTrigger` opening tag, whole, so its attributes can be read together.
TAB_TRIGGER = re.compile(r"<TabTrigger\b[^>]*?/?>", re.S)
TAB_ICON = re.compile(r'(?<![\w-]):?icon(-left)?="')


@pytest.mark.parametrize("app", APPS)
def test_every_tab_carries_an_icon(app):
	"""A strip of bare words is a strip that reads as unfinished.

	Every tab in either SPA has a glyph, and none of them is typed twice: the
	four over a record and the doctype's own Tab Breaks all resolve through
	`tabIcon`, which derives one from the tab's own label — Frappe has no icon
	property on a Tab Break, so a doctype we do not own would otherwise have
	nothing to offer. The operator console's tabs name theirs directly, because
	those are eight hand-written pages rather than a list of labels.

	What this catches is the fifth tab added without one. That is the whole
	failure mode: a tab strip where three carry an icon and the fourth does not
	reads as a tab that failed to load rather than as a tab with no icon.
	"""
	root = ROOT / f"apps/{app}/frontend/src"
	offenders = []
	for path in sorted(root.rglob("*.vue")):
		source = path.read_text()
		for match in TAB_TRIGGER.finditer(source):
			if TAB_ICON.search(match.group(0)):
				continue
			line = source[: match.start()].count("\n") + 1
			offenders.append(f"{path.relative_to(root)}:{line}")
	assert not offenders, (
		"these tabs carry no icon — give them one, or `tabIcon(label)` where "
		"the label is the doctype's: " + ", ".join(offenders)
	)
