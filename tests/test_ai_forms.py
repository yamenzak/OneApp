"""What a model may ask a form to be, and what it still may not.

`docs/ONEFORMS.md` stage 8. This is the first kind on the registry that builds
a *surface* rather than a record — a page strangers open, and a stylesheet
their browser runs — so the two claims worth holding are not about the card:

  * **The rules are not relaxed for a model.** `service._admin` and
    `service._over` are asked when the card is *proposed*, so a model that
    offered a form over Salary Slip is told on the turn it tried. A card that
    checked on Apply would have told somebody they could do something they
    could not.
  * **The stylesheet goes through the same door a person's does.**
    `service.check_css` refuses an `@import`, a `url()` to another site and
    anything that closes the element, whoever wrote it.

And one that is about the card: the whole stylesheet, and every field, is on
it before anybody presses Apply. `test_ai_document.py` is the pattern and says
why.
"""

import ast
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/oneforms/actions.py"
HOOKS = ROOT / "apps/oneapp/oneapp/hooks.py"
BUILDER = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/FormBuilder.vue"
PUBLIC = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/PublicForm.vue"
CLIENT = ROOT / "apps/oneapp/frontend/src/shared/lib/workspace/forms.js"


class Row(dict):
	def __getattr__(self, name):
		return self.get(name)

	def insert(self, **kw):
		self.setdefault("name", f"sug-{len(STORED) + 1}")
		STORED[self["name"]] = self
		return self

	def db_set(self, values, **kw):
		self.update(values)


STORED: dict[str, Row] = {}

#: What the doctype has, as `service.available` reads it off the meta.
FIELDS = [
	{"fieldname": "applicant_name", "label": "Name", "fieldtype": "Data",
	 "reqd": 1, "options": ""},
	{"fieldname": "email_id", "label": "Email", "fieldtype": "Data",
	 "reqd": 0, "options": ""},
	{"fieldname": "cover_letter", "label": "Cover letter",
	 "fieldtype": "Text", "reqd": 0, "options": ""},
]


@pytest.fixture
def ai(stub_frappe, monkeypatch):
	for name in list(sys.modules):
		if name.startswith("oneapp.onespace") or name.startswith("oneapp.oneforms"):
			del sys.modules[name]

	STORED.clear()

	stub_frappe.get_doc = lambda first, *a, **k: (
		Row(first) if isinstance(first, dict) else STORED.get(a[0])
	)
	stub_frappe.get_all = lambda *a, **k: []
	stub_frappe.db.savepoint = lambda *a, **k: None
	stub_frappe.db.release_savepoint = lambda *a, **k: None
	stub_frappe.db.rollback = lambda *a, **k: None
	stub_frappe.db.get_value = lambda *a, **k: ""
	stub_frappe.has_permission = lambda *a, **k: True
	stub_frappe.utils.now = lambda: "2026-09-18 08:00:00"

	from oneapp.oneai import actions
	from oneapp.oneforms import actions as module, service

	from oneapp.onespace.workspace import OWNER_ROLE
	stub_frappe.get_roles = lambda *a, **k: [OWNER_ROLE]

	built = []
	monkeypatch.setattr(service, "finding", types.SimpleNamespace(placed=lambda: {
		"Job Applicant": {"doctype": "Job Applicant", "space": "onehr",
		                  "space_label": "OnePeople", "screen": "applicants",
		                  "label": "Job Applicant", "icon": "lucide-users"},
	}))
	monkeypatch.setattr(service, "available", lambda doctype: list(FIELDS))
	monkeypatch.setattr(service, "make", lambda doctype, title="": (
		built.append({"what": "make", "doctype": doctype, "title": title})
		or {"name": "WF-1", "route": "apply", "title": title}))
	monkeypatch.setattr(service, "layout", lambda name, fields: (
		built.append({"what": "layout", "fields": fields}) or {"name": name}))
	monkeypatch.setattr(service, "settings", lambda name, values: (
		built.append({"what": "settings", "values": values}) or {"name": name}))
	monkeypatch.setattr(service, "_ours", lambda name: types.SimpleNamespace(
		name=name, title="Apply to us"))
	monkeypatch.setattr(service, "style", lambda name, css: (
		built.append({"what": "style", "css": css}) or {"name": name}))

	return types.SimpleNamespace(
		module=module, service=service, actions=actions, frappe=stub_frappe,
		monkeypatch=monkeypatch, built=built, kept=STORED,
	)


def ask(ai, **kw):
	said = {"doctype": "Job Applicant", "title": "Apply to us",
	        "access": "anyone", "introduction": "Tell us about yourself.",
	        "fields": [{"fieldname": "applicant_name", "label": "Your name"},
	                   {"fieldname": "cover_letter", "label": "Why you",
	                    "reqd": 1}]}
	said.update(kw)
	return ai.actions.propose("forms.build", said, session="s1", about=("", ""))


def dress(ai, css):
	return ai.actions.propose("forms.style", {"form": "WF-1", "css": css},
	                          session="s1", about=("", ""))


# --------------------------------------------------------------------------- #
# The rules, asked when it is proposed
# --------------------------------------------------------------------------- #

def test_asking_builds_nothing(ai):
	answered = ask(ai)

	assert answered["proposed"] in ai.kept
	assert ai.built == []
	assert "waiting" in answered["note"]


def test_a_doctype_no_space_of_theirs_shows_is_refused_on_the_turn_it_is_asked(ai):
	"""The failure the whole module exists to prevent, reached through a model.

	Not on Apply. A card offering a form over Salary Slip, which then refused
	when somebody pressed the button, would have told them they could publish
	a page past every grant in the product.
	"""
	answered = ask(ai, doctype="Salary Slip")

	assert "Salary Slip" in answered["error"]
	assert ai.kept == {}


def test_a_member_cannot_propose_one_either(ai):
	ai.frappe.get_roles = lambda *a, **k: ["Space-User"]
	assert "admin" in ask(ai)["error"].lower()
	assert "admin" in dress(ai, "h1 { color: red }")["error"].lower()
	assert ai.kept == {}


def test_a_field_the_doctype_has_not_got_is_refused(ai):
	answered = ask(ai, fields=[{"fieldname": "salary", "label": "Salary"}])
	assert "salary" in answered["error"]


def test_a_form_that_asks_nothing_is_refused(ai):
	assert "asks" in ask(ai, fields=[])["error"]


def test_who_may_reach_it_is_one_word_rather_than_three_switches(ai):
	"""Three booleans that contradict each other is a page that refuses
	everyone, which is a state nobody meant and Frappe will not resolve."""
	assert "anyone" in ask(ai, access="sort-of")["error"]

	for word, expected in (("anyone", 1), ("signed-in", 0), ("invitation", 0)):
		ai.built.clear()
		STORED.clear()
		ai.actions.apply(ask(ai, access=word)["proposed"])
		values = next(one for one in ai.built if one["what"] == "settings")["values"]
		assert values["anonymous"] == expected
		assert sum(values[key] for key in
		           ("anonymous", "login_required", "key_required")) == 1


def test_a_field_the_doctype_insists_on_stays_required(ai):
	"""The same rule `layout` keeps one level down, so a card cannot show a
	person an optional field that the save will reject as missing."""
	name = ask(ai, fields=[{"fieldname": "applicant_name", "label": "Name",
	                        "reqd": 0}])["proposed"]
	said = ai.actions._read(ai.kept[name].payload)
	assert said["fields"][0]["reqd"] == 1


# --------------------------------------------------------------------------- #
# The card shows the form, not a count of it
# --------------------------------------------------------------------------- #

def test_every_field_is_on_the_card(ai):
	name = ask(ai)["proposed"]
	kind = ai.actions.get("forms.build")
	said = kind.rows(ai.actions._read(ai.kept[name].payload), {})

	asks = next(one for one in said if one["label"] == "Asks for")
	assert "Your name" in asks["now"] and "Why you" in asks["now"]
	# And required is marked, because it is the difference between a page
	# somebody can send and one that refuses them.
	assert "Your name *" in asks["now"]
	assert not any("2 fields" in str(one.get("now")) for one in said)


def test_the_card_says_what_it_would_make_and_who_could_reach_it(ai):
	name = ask(ai)["proposed"]
	kind = ai.actions.get("forms.build")
	said = ai.actions._read(ai.kept[name].payload)
	rows = {one["label"]: one["now"] for one in kind.rows(said, {})}

	assert rows["Makes a"] == "Job Applicant"
	assert rows["Who can reach it"] == "Anyone with the link"
	assert kind.summarise(said, {}).startswith("Build Apply to us")


# --------------------------------------------------------------------------- #
# Applying goes the way a person would have gone
# --------------------------------------------------------------------------- #

def test_applying_is_the_same_four_calls_the_builder_posts_to(ai):
	done = ai.actions.apply(ask(ai)["proposed"])

	assert done["ok"] and done["name"] == "WF-1"
	assert [one["what"] for one in ai.built] == ["make", "layout", "settings"]
	assert ai.built[0]["doctype"] == "Job Applicant"
	assert [one["fieldname"] for one in ai.built[1]["fields"]] == \
		["applicant_name", "cover_letter"]


def test_what_it_made_is_a_draft_and_the_card_says_where_it_is(ai):
	"""Unpublished, like every other new form. A model that could publish one
	would be a model that opened a workspace to strangers on its own say-so."""
	opens = ai.actions.apply(ask(ai)["proposed"])["opens"]

	assert opens["href"] == "/one/forms/WF-1"
	assert not any("published" in str(one.get("values") or {}) for one in ai.built)


# --------------------------------------------------------------------------- #
# The stylesheet
# --------------------------------------------------------------------------- #

def test_the_model_is_held_to_the_same_stylesheet_rules_a_person_is(ai):
	"""One door, `service.check_css`, and the model goes through it at proposal
	time. A second copy of these rules here would be a second set of bugs and
	only one of them would get fixed."""
	assert "@import" in dress(ai, "@import url(https://x/y.css);")["error"]
	assert "url()" in dress(ai, "body { background: url(https://x/y.png) }")["error"]
	assert "markup" in dress(ai, "body {} </style><script>")["error"]
	assert ai.kept == {}

	# And the one that is a picture rather than a call.
	assert dress(ai, "body { background: url(data:image/gif;base64,R0lGOD) }").get("proposed")


def test_an_empty_stylesheet_is_refused(ai):
	assert "empty" in dress(ai, "   ")["error"]


def test_the_card_shows_the_whole_sheet_against_what_is_there(ai):
	ai.frappe.db.get_value = lambda *a, **k: "h1 { color: blue }"
	name = dress(ai, "h1 { color: red }")["proposed"]
	kind = ai.actions.get("forms.style")
	[row] = kind.rows(ai.actions._read(ai.kept[name].payload),
	                  ai.actions._read(ai.kept[name].before))

	assert row["was"] == "h1 { color: blue }"
	assert row["now"] == "h1 { color: red }"


def test_applying_a_restyle_goes_through_the_service(ai):
	done = ai.actions.apply(dress(ai, "h1 { color: red }")["proposed"])

	assert done["ok"]
	assert ai.built == [{"what": "style", "css": "h1 { color: red }"}]


# --------------------------------------------------------------------------- #
# The tools
# --------------------------------------------------------------------------- #

def test_a_refusal_keeps_the_sentence_the_service_wrote(ai):
	"""`propose` turns a `PermissionError` into "That is not yours to change",
	which is the right answer for a record and useless to a model that named a
	doctype wrongly — so `_asked` keeps the sentence the rule wrote."""
	answered = ask(ai, doctype="Salary Slip")
	assert "not yours to change" not in answered["error"]


def test_the_listing_says_no_rather_than_throwing(ai):
	ai.frappe.get_roles = lambda *a, **k: ["Space-User"]
	found = ai.module.the_forms_of_this_workspace.func()

	assert found["could_be_made_over"] == []
	assert "admin" in found["reason"]


def test_the_listing_carries_the_fields_so_the_model_need_not_guess(ai):
	found = ai.module.the_forms_of_this_workspace.func()
	[over] = found["could_be_made_over"]

	assert over["doctype"] == "Job Applicant"
	assert over["space_label"] == "OnePeople"
	assert [one["fieldname"] for one in over["fields"]] == \
		["applicant_name", "email_id", "cover_letter"]
	assert over["fields"][0]["required"] is True


def test_the_tools_are_the_registry_and_add_nothing(ai):
	"""Wrappers, like every other proposing tool. A second implementation of
	the check is a second set of bugs."""
	assert "forms.build" in ai.module.propose_form.func.__code__.co_consts
	assert "forms.style" in ai.module.propose_form_styling.func.__code__.co_consts


def test_no_tool_writes(ai):
	"""Read off the tree. The whole argument is that a model proposes and a
	person applies, and one `@tool` that called `service.make` would end it."""
	tree = ast.parse(SOURCE.read_text())
	for node in ast.walk(tree):
		if not isinstance(node, ast.FunctionDef):
			continue
		if not any(ast.unparse(one) == "tool" for one in node.decorator_list):
			continue
		called = {ast.unparse(inner.func) for inner in ast.walk(node)
		          if isinstance(inner, ast.Call)}
		assert not called & {"service.make", "service.layout", "service.settings",
		                     "service.style"}, f"{node.name} writes"


def test_both_hooks_name_it(ai):
	"""A kind that only registers when something imports its module is a card
	that fails to apply on a cold worker — `actions.discover` says so."""
	source = HOOKS.read_text()
	assert '"oneapp.oneforms.actions.tools"' in source
	assert '"oneapp.oneforms.actions"' in source


# --------------------------------------------------------------------------- #
# The other half — a person writing the same stylesheet
# --------------------------------------------------------------------------- #

def test_the_builder_opens_onecodes_editor_over_it(ai):
	"""The same editor the Drive opens a `.py` in. A second code box in this
	product would be a second set of keybindings for the same job."""
	source = BUILDER.read_text()
	assert "CodeDialog" in source and 'language="css"' in source
	assert "formStyle" in source


def test_the_stylesheet_is_its_own_door_rather_than_a_setting(ai):
	"""Code on a page strangers load does not ride in with the button label."""
	from oneapp.oneforms import service as real

	assert "custom_css" not in real.SETTINGS
	assert "custom_css" not in CLIENT.read_text().split("formSettings")[1][:200]


def test_the_public_page_wears_it_and_takes_it_off_again(ai):
	"""Put in the document rather than the template, so it has to be removed:
	navigating off a styled form must not leave its rules on the next page."""
	source = PUBLIC.read_text()
	assert "onBeforeUnmount" in source and "sheet?.remove()" in source
	assert 'dress(form.value.css)' in source


def test_the_page_has_hooks_a_stylesheet_can_hold_on_to(ai):
	"""Tailwind utilities are not an API. Three named things that will not move
	when somebody reflows the page, and the tool description names them."""
	source = PUBLIC.read_text()
	for slot in ("public-form", "form-title", "form-introduction"):
		assert f'data-slot="{slot}"' in source
		assert slot in SOURCE.read_text()


def test_there_is_no_door_for_javascript(ai):
	"""Not caution — `client_script` is written against `frappe.web_form.on`, a
	runtime Frappe's Jinja page has and this Vue one does not. Giving it one
	means shipping a script evaluator to a stranger's browser, which is a
	bigger decision than letting somebody style a page."""
	assert "client_script" not in SOURCE.read_text()
	assert "client_script" not in CLIENT.read_text()


def test_a_stylesheet_that_moved_since_is_refused_rather_than_overwritten(ai):
	"""`actions.py`'s second rule, and a replace rather than a patch is where
	it bites: the card compared against what was there, and that is no longer
	what is there."""
	ai.frappe.db.get_value = lambda *a, **k: "h1 { color: blue }"
	name = dress(ai, "h1 { color: red }")["proposed"]

	ai.frappe.db.get_value = lambda *a, **k: "h1 { color: green }"
	done = ai.actions.apply(name)

	assert not done["ok"]
	assert "changed since" in done["error"]
	assert ai.built == []
