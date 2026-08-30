"""The doctype JSONs are generated, and the generator has to still be runnable.

`scripts/gen_doctypes.py` writes every doctype in both apps. That only helps
while the two agree: the moment a field is added to a JSON by hand, running the
generator deletes it, and nothing says so until a site is installed without it.

This is how that was found. `view_type`, `view_settings`, `icon`, `logo` and
`view_types` had all been added to the files rather than to the generator, and
the generator had meanwhile been taught a module name — "OneSpace Core" — that
`apps/oneapp/oneapp/modules.txt` does not have, so running it would have
detached every tenant doctype from its module.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


@pytest.fixture(scope="module")
def gen():
	sys.path.insert(0, str(SCRIPTS))
	spec = importlib.util.spec_from_file_location("gen_doctypes", SCRIPTS / "gen_doctypes.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def _path(gen, name):
	pkg, module_dir, _ = gen.APPS[gen.DOCTYPES[name]["app"]]
	slug = name.lower().replace(" ", "_")
	return ROOT / "apps" / pkg / pkg / module_dir / "doctype" / slug / f"{slug}.json"


def test_every_doctype_on_disk_is_what_the_generator_would_write(gen):
	drifted = []
	for name, spec in gen.DOCTYPES.items():
		path = _path(gen, name)
		if not path.exists():
			drifted.append(f"{name}: {path} does not exist")
			continue
		if json.loads(path.read_text()) != gen.build(spec):
			drifted.append(name)
	assert not drifted, (
		"these files are not what `python3 scripts/gen_doctypes.py` writes, so "
		"running it would silently change them: " + ", ".join(drifted)
	)


def test_the_module_name_is_one_the_app_actually_declares(gen):
	"""A Frappe module name is plumbing: it has to match `modules.txt` and the
	directory beside it. A doctype in a module the app does not declare is a
	doctype the installer cannot place."""
	for key, (pkg, _module_dir, module_name) in gen.APPS.items():
		declared = (ROOT / "apps" / pkg / pkg / "modules.txt").read_text().split("\n")
		assert module_name in [line.strip() for line in declared if line.strip()], (
			f"{key}: the generator writes module {module_name!r}, which "
			f"apps/{pkg}/{pkg}/modules.txt does not declare"
		)
