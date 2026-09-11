"""The rule the whole arc rests on, read back off the source.

`docs/AI.md` §4 states it in one sentence: **the spine is in `onespace/ai/`
and knows nothing about mail, documents or sheets; a module declares its own
features and its own tools and knows nothing about the gateway.** That is the
difference between five surfaces sharing one thing and five surfaces each with
their own — and it is exactly the kind of rule that survives a review and dies
to the sixth surface in a hurry.

So it is a test. Static, over the import statements and the decorator calls,
because the claim is about what a file may reach for rather than about what it
does at run time — and because a test that had to boot Frappe to check a
layering rule would be a test nobody runs.
"""

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "apps/oneapp/oneapp"
SPINE = APP / "onespace/ai"

#: The apps a module owns. The spine may not reach into any of them.
MODULES = ("onemail", "onedoc", "onesheet", "onecalendar", "onestorage",
           "onemobility", "onecode")

#: The one file in the spine that may, and the reason is in its own docstring:
#: `kinds.py` holds the suggestion kinds for the framework's own nouns — a
#: record, a date in a diary, a task — and a diary entry is `onecalendar`'s.
#: Named one file at a time, so the next one has to argue its case here.
MAY_REACH_A_MODULE = {"kinds.py"}

#: What a module may use the gateway for. Everything else goes through the
#: `@ai_feature` decorator, which is what applies the workspace's model
#: choice, its ceiling and its credit hold — a module calling `gateway.call`
#: would be a module spending credits nobody priced.
GATEWAY_SURFACE = {"unstreamed", "deltas_to", "is_configured", "OutOfCredits",
                   "AIError"}


def sources(where: pathlib.Path):
	return sorted(p for p in where.rglob("*.py") if "__pycache__" not in p.parts)


def tree(path: pathlib.Path) -> ast.Module:
	return ast.parse(path.read_text(encoding="utf-8"))


def imported(node: ast.Module) -> list[str]:
	"""Every dotted path this module imports, including inside a function."""
	found = []
	for one in ast.walk(node):
		if isinstance(one, ast.Import):
			found += [alias.name for alias in one.names]
		elif isinstance(one, ast.ImportFrom) and one.module:
			found.append(one.module)
	return found


# --------------------------------------------------------------------------- #
# The spine knows nothing about a module
# --------------------------------------------------------------------------- #

def test_the_spine_does_not_import_a_module():
	"""A spine that imported mail would be a spine mail could break, and the
	next surface would find half of it already shaped around a mailbox."""
	reached = []
	for path in sources(SPINE):
		if path.name in MAY_REACH_A_MODULE:
			continue
		for one in imported(tree(path)):
			if any(one.startswith(f"oneapp.{module}") for module in MODULES):
				reached.append(f"{path.name} -> {one}")

	assert not reached, (
		"the spine reached into a module: " + ", ".join(reached)
		+ " — see docs/AI.md §4"
	)


def test_the_file_that_may_is_the_one_that_says_why():
	"""The exception is a file, not a habit. It has to carry the argument."""
	for name in MAY_REACH_A_MODULE:
		said = ast.get_docstring(tree(SPINE / name)) or ""
		assert "module" in said.lower(), f"{name} reaches a module and does not say why"


# --------------------------------------------------------------------------- #
# A module knows nothing about the gateway
# --------------------------------------------------------------------------- #

def declares_a_feature(node: ast.Module) -> bool:
	"""Whether this file actually decorates something with `@ai_feature`.

	The decorator and not the string: `hooks.py` and two package docstrings
	name it in prose, and a guard that counted those would be a guard whose
	failures are about comments.
	"""
	return any(
		isinstance(one, ast.FunctionDef) and any(
			getattr(getattr(d, "func", d), "id", getattr(getattr(d, "func", d), "attr", ""))
			== "ai_feature"
			for d in one.decorator_list
		)
		for one in ast.walk(node)
	)


def module_ai_files() -> list[pathlib.Path]:
	"""Every file outside the spine that declares an AI feature."""
	return [
		path for path in sources(APP)
		if SPINE not in path.parents and declares_a_feature(tree(path))
	]


def test_there_are_modules_declaring_features():
	"""Otherwise every test below passes by finding nothing."""
	assert len(module_ai_files()) >= 3


@pytest.mark.parametrize("path", module_ai_files(), ids=lambda p: p.name)
def test_a_module_reaches_the_gateway_only_for_what_the_decorator_cannot_do(path):
	"""`unstreamed` and the two exceptions, and nothing else.

	A module calling `gateway.call` would be a module spending credits the
	workspace never priced: the hold, the model choice and the ceiling are
	all applied by the callable the decorator injects.
	"""
	used = {
		one.attr for one in ast.walk(tree(path))
		if isinstance(one, ast.Attribute)
		and isinstance(one.value, ast.Name) and one.value.id == "gateway"
	}

	assert used <= GATEWAY_SURFACE, (
		f"{path.name} uses gateway.{', gateway.'.join(sorted(used - GATEWAY_SURFACE))}"
	)


# --------------------------------------------------------------------------- #
# Nothing declares a feature the registry will not find
# --------------------------------------------------------------------------- #

def hooked(name: str) -> list[str]:
	"""One list out of `hooks.py`, read as source.

	Read rather than imported because importing hooks pulls in Frappe, and
	this file's whole argument is that a layering rule should be checkable
	without a bench.
	"""
	said = (APP / "hooks.py").read_text(encoding="utf-8")
	block = re.search(rf"^{name} = \[(.*?)^\]", said, re.S | re.M)
	return re.findall(r'"([^"]+)"', block.group(1)) if block else []


def dotted(path: pathlib.Path) -> str:
	return "oneapp." + ".".join(path.relative_to(APP).with_suffix("").parts)


@pytest.mark.parametrize("path", module_ai_files(), ids=lambda p: p.name)
def test_every_module_that_declares_a_feature_is_in_the_hook(path):
	"""A feature that registers only when something happens to import its
	module is a feature missing from the settings page on a cold worker —
	which is `features.discover`'s whole argument."""
	assert dotted(path) in hooked("ai_features")


def test_every_module_that_registers_a_kind_is_in_the_hook():
	"""The same failure one layer over: a card that cannot be applied because
	the worker never imported the handler."""
	missing = []
	for path in sources(APP):
		said = path.read_text(encoding="utf-8")
		if "register(" not in said or "ai.actions" not in said:
			continue
		if dotted(path) not in hooked("ai_actions"):
			missing.append(dotted(path))

	assert not missing, "registers a kind and is not hooked: " + ", ".join(missing)


# --------------------------------------------------------------------------- #
# Every feature is priced
# --------------------------------------------------------------------------- #

def declarations():
	"""Every `@ai_feature(...)` call in the app, as `(file, keywords)`."""
	found = []
	for path in sources(APP):
		for node in ast.walk(tree(path)):
			if not isinstance(node, ast.Call):
				continue
			named = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
			if named != "ai_feature":
				continue
			found.append((path.name, {kw.arg: kw.value for kw in node.keywords}))
	return found


def test_there_are_features_to_check():
	assert len(declarations()) >= 6


@pytest.mark.parametrize("where,keywords", declarations(),
                         ids=lambda one: one if isinstance(one, str) else "")
def test_a_feature_declares_the_ceiling_it_is_held_against(where, keywords):
	"""A hold is priced off the declared ceiling before the call is made, so a
	feature that declared none reserves nothing and the workspace finds out
	what it cost afterwards."""
	assert "max_input_tokens" in keywords, f"{where}: no input ceiling"

	# An embedding has no output to bound — it answers with a vector of a
	# length the model decides — so the output ceiling is the one exception.
	if keywords.get("capability") and getattr(keywords["capability"], "value", "") \
			== "Text Embeddings":
		return
	assert "max_output_tokens" in keywords, f"{where}: no output ceiling"


@pytest.mark.parametrize("where,keywords", declarations(),
                         ids=lambda one: one if isinstance(one, str) else "")
def test_a_conversational_feature_bounds_the_whole_run(where, keywords):
	"""A turn is a whole call with its own hold, so `max_credits` bounds one
	turn and nothing bounds ten. `conversation.py` refuses to loop without
	`max_turns`; this catches it at the declaration instead."""
	if "tools" not in keywords:
		return
	assert "max_turns" in keywords, f"{where}: tools without a turn limit"
	assert "max_run_credits" in keywords, f"{where}: tools without a run ceiling"


# --------------------------------------------------------------------------- #
# Nothing holds a worker open
# --------------------------------------------------------------------------- #

#: The one surface that still answers inside the request, and it predates the
#: run spine. `chat/assistant.send` is a tool-using conversation whose reply
#: is the transcript, and `streaming.py`'s own docstring names it: it refuses
#: to stream, so it holds a gunicorn worker for the length of a generation.
#: Moving it onto `streaming.begin` is the first thing in `docs/AI.md` §6's
#: list of what is not built. Named here so that adding a *second* one is a
#: decision somebody has to make in this file.
MAY_ANSWER_IN_THE_REQUEST = {"assistant.py"}


@pytest.mark.parametrize("path", module_ai_files(), ids=lambda p: p.name)
def test_a_whitelisted_endpoint_does_not_call_a_feature_inline(path):
	"""A generation is two to forty seconds and a shard has four gunicorn
	workers. Every surface begins a run through `streaming.begin` and hands
	back an id — see `onespace/ai/streaming.py`.

	Checked by name: the features a file declares are the functions it must
	not call from inside a whitelisted one.
	"""
	if path.name in MAY_ANSWER_IN_THE_REQUEST:
		pytest.skip("predates the run spine — see MAY_ANSWER_IN_THE_REQUEST")
	node = tree(path)
	features = {
		one.name for one in ast.walk(node)
		if isinstance(one, ast.FunctionDef)
		and any(getattr(d.func, "id", getattr(d.func, "attr", "")) == "ai_feature"
		        for d in one.decorator_list if isinstance(d, ast.Call))
	}

	called = []
	for one in ast.walk(node):
		if not (isinstance(one, ast.FunctionDef) and _whitelisted(one)):
			continue
		for inner in ast.walk(one):
			if isinstance(inner, ast.Call) and getattr(inner.func, "id", "") in features:
				called.append(f"{one.name} -> {inner.func.id}")

	assert not called, (
		f"{path.name} runs a feature inside a request: " + ", ".join(called)
	)


def _whitelisted(node: ast.FunctionDef) -> bool:
	for one in node.decorator_list:
		func = one.func if isinstance(one, ast.Call) else one
		if getattr(func, "attr", "") == "whitelist":
			return True
	return False
