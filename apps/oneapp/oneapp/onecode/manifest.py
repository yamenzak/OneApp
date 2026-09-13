"""What a tenant project declares, and what declaring it is allowed to buy.

`docs/UNIFICATION.md` §E9's second rail, and the one the section exists for.
Frappe's `Web Page` has a `context_script` — a Python field that runs with the
whole framework in scope before the template renders. It is exactly the hook a
tenant app needs and it is exactly the hook a tenant may never have, because a
tenant who can write server Python on their own site can write it on ours.

So the shape is the one the platform already uses for a Space: **a manifest
names what it needs, and the server builds the context from the declaration.**
`onestorage/linked.py` states the doctrine this inherits — *nothing here takes
a doctype, a filter or a fieldname from the caller* — and the difference
between that and a script is the whole of the security story: a declaration is
a list the server checks, and a script is a list the server runs.

## The file

`onecode.json`, in the project's own folder in the Drive. Nothing else makes a
folder a project; there is no second store and no row to keep in step, which is
E1's argument arriving where §E9 said it would.

	{
	  "name": "Storefront",
	  "route": "shop",
	  "engine": "preact",
	  "entry": "main.js",
	  "reads": ["Item", "Item Price"],
	  "calls": ["oneapp.onespace.spaceview.list_view"]
	}

Every key is required except `reads` and `calls`, which default to nothing —
the direction worth failing in, since a project that declares nothing renders
and reaches no data rather than the other way round.

## What the keys cost

`reads` is the one that matters. A doctype here is not a grant: it is a name
the shell will put in the boot context, and every read still goes through the
reader's own permissions, so a project declaring `Salary Slip` gives its author
nothing their account did not already have. What the declaration buys is that
the *page* knows which doctypes it is about without asking the caller, which is
what makes the context buildable without a script.

`calls` is narrower still, and deliberately so: a whitelisted method on one of
this platform's own apps. Not `frappe.client.*`, which is the generic door —
a project that needs it does not need a manifest, it needs the desk.
"""

import json
import re

from . import engines, routes

#: Keys a manifest may carry. Anything else is refused by name, rather than
#: ignored: a typo silently dropped is a project whose author is looking at the
#: wrong file for an hour.
KEYS = ("name", "route", "engine", "entry", "reads", "calls")

REQUIRED = ("name", "route", "engine", "entry")

#: Keys that exist, are tempting, and are refused with the reason. Each of
#: these is a real field on Frappe's `Web Page` and each is a server-side hook;
#: a manifest that carries one is not a mistake to be ignored but an attempt to
#: be answered.
REFUSED = {
	"context_script": (
		"A project's context comes from what it declares — `reads` and "
		"`calls` — and never from code the server runs. See "
		"docs/UNIFICATION.md §E9."
	),
	"javascript": "Put JavaScript in the project's own files, not in the manifest.",
	"dynamic_template": "The shell is ours; a project declares its entry file.",
	"content_type": "A project is served as a page. There is no second answer.",
}

#: The prefixes a declared `calls` entry may start with. Ours, and nothing
#: else: `frappe.client.*` and `frappe.desk.*` are the generic doors, and a
#: project that wants one of them wants the desk rather than a page.
CALLABLE = ("oneapp.", "oneapp_control.")

#: Whitelisted or not, these are refused. Each hands out something a
#: declaration cannot make safe, and the list is short because the rule above
#: already excludes the framework — these are ours and still not a project's.
NEVER_CALLED = (
	# The permission system. `test_manifests.py` keeps the same rule for a
	# Space's manifest; this is that rule, one layer out.
	"oneapp.onespace.roles",
	"oneapp.onespace.permissions",
	# The AI gateway spends the workspace's credits.
	"oneapp.onespace.ai.gateway",
	# The control plane. A tenant page has no business reaching the thing that
	# provisions tenants.
	"oneapp_control.provisioning",
	"oneapp_control.billing",
)

#: A project name is what appears in the workspace's own list of them. Kept
#: short and printable rather than free text: it lands in error messages, in
#: the route registry's collision sentence, and in a folder name.
NAME = re.compile(r"^[\w][\w .'-]{0,59}$")

#: The entry is a path inside the project's own folder. No `..`, no leading
#: slash, and a real module extension — the shell puts it in a `<script
#: type="module" src>` and a `.png` there is a page that loads nothing.
ENTRY = re.compile(r"^[\w][\w./-]*\.(?:js|mjs)$")

FILENAME = "onecode.json"


class Invalid(ValueError):
	"""A manifest that cannot be saved, with the reason a person reads."""


def parse(text: str) -> dict:
	try:
		found = json.loads(text or "")
	except json.JSONDecodeError as error:
		raise Invalid(f"{FILENAME} is not valid JSON: {error.msg}, line {error.lineno}.")
	if not isinstance(found, dict):
		raise Invalid(f"{FILENAME} holds a {type(found).__name__}, not an object.")
	return found


def validate(declared: dict, taken: dict | None = None) -> dict:
	"""Check one manifest and answer the normalised form.

	`taken` is the route registry — `{route: project}` — for the collision
	check. Left out when there is nothing to collide with, which is the case
	the guards exercise and not one a running site has.
	"""
	for key in REFUSED:
		if key in declared:
			raise Invalid(f"`{key}` is not a key a project may declare. {REFUSED[key]}")

	unknown = sorted(set(declared) - set(KEYS))
	if unknown:
		raise Invalid(
			f"{FILENAME} declares {', '.join(unknown)}, which "
			f"{'mean' if len(unknown) > 1 else 'means'} nothing here. "
			f"The keys are: {', '.join(KEYS)}."
		)

	missing = [key for key in REQUIRED if not declared.get(key)]
	if missing:
		raise Invalid(f"{FILENAME} is missing {', '.join(missing)}.")

	name = str(declared["name"]).strip()
	if not NAME.match(name):
		raise Invalid(f"“{name}” is not a project name. Letters, digits, spaces and .'- , up to 60.")

	engine = str(declared["engine"]).strip()
	if engine not in engines.OFFERED:
		raise Invalid(
			f"“{engine}” is not an engine this workspace serves. "
			f"Pick one of: {', '.join(engines.OFFERED)}."
		)

	# One leading `./` removed, not every leading `.` and `/` there is:
	# `lstrip("./")` turns `../../etc/passwd.js` into `etc/passwd.js`, which
	# passes both checks below. It did, for about ten minutes.
	entry = str(declared["entry"]).strip()
	if entry.startswith("./"):
		entry = entry[2:]
	if ".." in entry or entry.startswith("/") or not ENTRY.match(entry):
		raise Invalid(f"“{entry}” is not a file inside the project. Name a .js in the project's folder.")

	reads = _list(declared.get("reads"), "reads")
	calls = _list(declared.get("calls"), "calls")
	for method in calls:
		if not method.startswith(CALLABLE):
			raise Invalid(
				f"“{method}” is not a method a project may call. Declared "
				f"methods start with {' or '.join(CALLABLE)}."
			)
		if method.startswith(NEVER_CALLED):
			raise Invalid(f"“{method}” is not a method a project may call, declared or not.")

	route = routes.check(declared["route"], taken or {})

	return {
		"name": name, "route": route, "engine": engine, "entry": entry,
		"reads": reads, "calls": calls,
	}


def _list(value, key: str) -> list[str]:
	if value is None:
		return []
	if not isinstance(value, list) or not all(isinstance(one, str) for one in value):
		raise Invalid(f"`{key}` is a list of strings.")
	return [one.strip() for one in value if one.strip()]


def context(declared: dict, reader=None) -> dict:
	"""What the shell puts in front of a project's code.

	Built from the declaration and from the reader — never from the request. A
	project's own code decides nothing about what is in here, which is the
	whole point: the answer to *what can a tenant's code reach* is **nothing it
	is not handed**, and this function is the handing.

	`reads` reaches the page as names only. The page still fetches through the
	ordinary API under the reader's own permissions; what the declaration saves
	is the page having to ask the caller what it is about.
	"""
	import frappe

	who = reader or frappe.session.user
	return {
		"project": declared["name"],
		"route": declared["route"],
		"engine": declared["engine"],
		"entry": declared["entry"],
		"reads": list(declared.get("reads") or []),
		"calls": list(declared.get("calls") or []),
		"imports": engines.import_map(declared["engine"]),
		"user": who,
	}
