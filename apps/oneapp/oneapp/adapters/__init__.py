"""What we change about somebody else's app, in one place per app.

`docs/CLEANUP.md` §7 and stage 10. This product is built over three apps it
does not own — Frappe, ERPNext and HRMS — and the changes it makes to them are
real: seven doctypes whose controller is ours, fourteen more we hook without
replacing, twenty-one we add fields to, and twenty-three of their functions we
call by name. Every one of those was a decision, and until now the only way to
find them was to grep.

**An adapter is a declaration, not a directory the code moved into.** That
distinction is the whole design and it is worth being blunt about, because the
plan's one-line version ("one directory per foreign app") reads like the other
thing.

`onetask/task.py`'s `ProjectTask` is *OneTask's behaviour*. It is a subclass of
ERPNext's Task because that is how Frappe lets you add behaviour to somebody
else's doctype, and moving it into `adapters/erpnext/` would file it by whose
schema it touches rather than by what it is for — which is the same mistake
§4 already made once with the nested module tree, in a different key. A reader
asking "what does a task do on save" would then have to know that the answer is
under ERPNext.

So the code stays where it belongs and these three files say **what** and
**why**, doctype by doctype and function by function. Nothing imports them at
runtime. `tests/test_adapters.py` holds them to `hooks.py`, to the space
manifests and to an import scan of the app, in both directions — so an adapter
cannot describe a seam that is gone, and a seam cannot exist without being
described.

That second direction is the one that earns this. Adding a `doc_events` entry
on `Sales Invoice` is two lines in `hooks.py` and, before this, invisible to
anybody asking what we do to ERPNext.

**Four declarations per app**, and each is a different kind of change:

* `SUBCLASSED` — their doctype, our controller. The heaviest thing we do: a
  method of ours runs instead of theirs, and an upgrade can silently change
  what we are overriding.
* `HOOKED` — their doctype, our handler beside theirs. Additive, and the
  failure mode is ours breaking their save rather than their behaviour going
  missing.
* `EXTENDED` — their doctype, our fields. Declared in the space manifests and
  applied by the tenant seeder; this is the list of which of their tables now
  carry a `custom_` column of ours.
* `CALLED` — their function, by dotted path. What we reuse rather than
  re-solve, and the list that breaks on an upgrade with an ImportError rather
  than quietly.

**This is the transpose of the module docs, not a replacement for them.** Every
module has a `docs/integrations.md` — `docs/CLEANUP.md` §8 — which answers
"what does OneHR reach". These answer "what reaches into HRMS". Both are
worth having and neither is derivable from the other by a reader in a hurry,
which is the whole reason the second one did not exist until somebody asked the
question the other way round.
"""

import importlib
import pathlib

#: The key each adapter declares itself under, and the app's name on disk.
APP = "APP"


def _modules() -> dict:
	"""Every adapter in this directory, keyed by the app it is about.

	Discovered the same way `oneapp_control/spaces/` discovers its manifests —
	`docs/CLEANUP.md` stage 9 — and for the same reason: a list of three that
	somebody has to remember to add a fourth to is a list that will be wrong
	the first time it matters.
	"""
	here = pathlib.Path(__file__).parent
	found = {}
	for path in sorted(here.glob("*.py")):
		if path.stem.startswith("_"):
			continue
		module = importlib.import_module(f"{__name__}.{path.stem}")
		app = getattr(module, APP, None)
		if not app:
			continue
		found[app] = module
	return found


ADAPTERS = _modules()


def owner_of(doctype: str) -> str | None:
	"""Which foreign app owns a doctype, or `None` for one of ours.

	Read off the adapters rather than off a bench, so it answers the same way
	in CI. A doctype named by two adapters is a mistake the guard catches
	rather than something this resolves — there is no sensible tiebreak
	between "this is ERPNext's" and "this is HRMS's".
	"""
	for app, module in ADAPTERS.items():
		if doctype in touched(module):
			return app
	return None


def touched(module) -> set[str]:
	"""Every doctype of one app we do anything to."""
	return (set(module.SUBCLASSED) | set(module.HOOKED)
	        | set(module.EXTENDED))


def everything() -> dict[str, set[str]]:
	"""Every foreign doctype we touch, by the app that owns it."""
	return {app: touched(module) for app, module in ADAPTERS.items()}
