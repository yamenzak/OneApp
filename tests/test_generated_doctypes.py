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

from doctype_paths import slug as doctype_slug

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
	slug = doctype_slug(name)
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


def test_no_doctype_is_maintained_by_hand(gen):
	"""The test above only sees doctypes the generator knows about.

	Which left the inverse hole, and something sat in it: `OneSpace Site State`
	was written by hand, so it was the one doctype whose file could drift from
	anything at all — the drift check iterates `DOCTYPES` and never noticed a
	directory that was not in it.

	So this walks the disk instead. Every doctype directory in either app has to
	be one the generator would write, which means a new doctype is declared in
	`scripts/gen_doctypes.py` or it fails here rather than silently becoming the
	next thing nothing checks.
	"""
	known = {doctype_slug(name) for name in gen.DOCTYPES}
	strays = []
	for pkg, module_dir, _ in gen.APPS.values():
		root = ROOT / "apps" / pkg / pkg / module_dir / "doctype"
		if not root.is_dir():
			continue
		for child in sorted(root.iterdir()):
			if not child.is_dir() or child.name.startswith("_"):
				continue
			if not (child / f"{child.name}.json").exists():
				continue
			if child.name not in known:
				strays.append(f"{pkg}/{module_dir}/doctype/{child.name}")
	assert not strays, (
		"these doctypes exist on disk but are not declared in "
		"scripts/gen_doctypes.py, so nothing checks them for drift: "
		+ ", ".join(strays)
	)
