"""The frontend guards.

Two SPAs have to look and behave like one product. They cannot share an npm
workspace, since each is mirrored to its own repository for Frappe Cloud, so the
shared setup is generated into both instead. These tests assert the guards that
make that hold.
"""

import json
import sys
from pathlib import Path

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
