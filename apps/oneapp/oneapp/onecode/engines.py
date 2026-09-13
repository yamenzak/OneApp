"""Which front-end libraries a tenant project may import, and at what version.

`docs/UNIFICATION.md` §E9's third rail. The requirement is **zero build**, and
the honest reading of that is that "buildless" is a property of the module
graph and not of the framework: native ES modules plus an import map will run
Preact or Vue or Lit without a bundler, and no amount of tooling choice changes
that. So the rail to lay is not *which engine* — it is that **the shell serves
an import map the workspace controls**, and the engine becomes a line in a
project's manifest rather than a decision baked into a loader.

Three things follow from that, and each is a rule below rather than a habit:

**Pinned.** Every entry names an exact version. A range is a project that
worked on Tuesday and does not on Wednesday, with nothing in the tenant's own
files changed to explain it.

**Ours.** Every entry is served from this workspace's own host. The CSP
argument and the offline argument are the same argument, and there is a third:
an import map pointing at a third-party CDN makes every tenant page's integrity
somebody else's operational decision. `assets` is where the bench already
serves our own static files, so a pinned copy lands there like everything else.

**Complete.** An engine the picker offers and the map does not carry is a
project that will not load, and it fails at the moment somebody opens the page
rather than at the moment somebody declared it. `tests/test_onecode.py` reads
this back against the offered list for exactly that reason — it is the same
shape of bug the language catalogue had, one list ahead of another.

Nothing here executes anything. A project's code is still bytes in the Drive;
this only says what its `import` statements are allowed to resolve to.
"""

#: Where a pinned copy is served from. Relative rather than absolute: the same
#: map has to work on `space.localhost:8001` and on a customer's own domain,
#: and a host written into it would be right on one of them.
ROOT = "/assets/oneapp/engines"

#: engine key -> (label, version, {specifier: file}).
#:
#: The specifier is what a tenant writes in an `import` statement; the file is
#: what it resolves to under `ROOT`. Two entries for Preact rather than one
#: because `htm` is what makes it buildless — JSX without a compiler — and a
#: person who picked Preact and cannot import `htm` has picked the wrong half.
ENGINES = {
	"preact": ("Preact", "10.26.4", {
		"preact": "preact-10.26.4.js",
		"preact/hooks": "preact-hooks-10.26.4.js",
		"htm/preact": "htm-preact-3.1.1.js",
	}),
	"vue": ("Vue", "3.5.13", {
		"vue": "vue-3.5.13.esm-browser.prod.js",
	}),
	"lit": ("Lit", "3.2.1", {
		"lit": "lit-3.2.1.js",
	}),
	"alpine": ("Alpine", "3.14.9", {
		"alpinejs": "alpine-3.14.9.esm.js",
	}),
	# No engine at all. Not an omission — a page that is three files of plain
	# DOM is the case this whole arrangement is cheapest for, and making it
	# pick a framework to say it does not want one would be the tax the rest
	# of the design exists to avoid.
	"none": ("None", "", {}),
}

#: What a project may write in its manifest.
OFFERED = tuple(ENGINES)


def version(engine: str) -> str:
	return ENGINES.get(engine, ("", "", {}))[1]


def imports(engine: str) -> dict:
	"""The `imports` half of an import map, for one engine.

	One engine per project rather than a union of every engine on the site: a
	map is served into the page, and a page that can resolve `vue` because
	another tenant's project wanted it is a page whose dependencies nobody
	declared.
	"""
	if engine not in ENGINES:
		raise ValueError(f"{engine} is not an engine this workspace serves")
	return {
		specifier: f"{ROOT}/{file}"
		for specifier, file in ENGINES[engine][2].items()
	}


def import_map(engine: str) -> dict:
	"""The whole map, ready to be JSON in a `<script type="importmap">`."""
	return {"imports": imports(engine)}
