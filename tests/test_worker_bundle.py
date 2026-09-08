"""The worker Cloudflare runs is the worker in this repository.

The control plane uploads one file through Cloudflare's API — `postal-mime` is
an import, and the API takes a bundle, not a directory. That bundle is
generated (`workers/email-inbound/build.mjs`) and checked in, for the same
reason the SPA's generated files are: the thing that runs has to be reviewable,
and a deployed control plane does not have `workers/` on disk to build from.

Generated and checked in is a pair that drifts, so this is the guard. Editing
the worker's source without rebuilding leaves the old bundle in place and the
old behaviour in production, with nothing failing anywhere.

    cd workers/email-inbound && npm install && npm run build
"""

import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "workers/email-inbound"
BUNDLE = ROOT / "apps/oneapp_control/oneapp_control/cloudflare/worker/email-inbound.js"
STAMP = BUNDLE.with_suffix(".sha256")

#: What went into the bundle. `package.json` is in here because a dependency
#: bump changes what is bundled without changing a line of ours.
SOURCES = ("src/index.js", "src/routing.js", "package.json")


def test_the_bundle_is_there():
	assert BUNDLE.exists(), (
		"the control plane has no worker to upload — run `npm run build` in "
		"workers/email-inbound"
	)
	assert STAMP.exists(), "the bundle has no stamp; rebuild it"


def test_the_bundle_matches_its_source():
	stamp = hashlib.sha256()
	for name in SOURCES:
		stamp.update(name.encode())
		stamp.update((SOURCE / name).read_bytes())

	assert stamp.hexdigest() == STAMP.read_text().strip(), (
		"the worker's source has moved since the bundle was built. Run:\n"
		"    cd workers/email-inbound && npm install && npm run build"
	)


@pytest.mark.parametrize("marker", [
	# One line from each source, so a bundle built from a different tree fails
	# rather than merely being stale.
	"Unknown recipient",
	"oneapp.onemail.inbound.receive",
	"X-OneSpace-Signature",
])
def test_the_bundle_holds_what_the_worker_does(marker):
	assert marker in BUNDLE.read_text(), f"the bundle does not contain {marker!r}"


def test_the_bundle_is_small_enough_to_upload():
	"""Cloudflare's script limit is 1 MB after compression, and this is 110 KB
	before it. The check exists so that adding a MIME library nobody measured
	fails here rather than at the first deploy."""
	assert BUNDLE.stat().st_size < 900_000
