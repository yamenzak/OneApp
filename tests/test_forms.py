"""A form is a door into a doctype, and the door has to be the right size.

`docs/ONEFORMS.md` stage 1. `Web Form` is the foundation because it already
does almost everything — a token per recipient, a guest submission, a list
scoped to one person's own records — and because it writes into an **ordinary
doctype**, which is the whole reason a form over Job Applicant makes a Job
Applicant that OnePeople's screens already show.

That last part is also the danger, and it is what these guards are about: a
`Web Form` can be pointed at *anything on the site*. Without a rule, publishing
one is a way past every grant in the product.

  * **A form may only be made over a doctype a space this person holds already
    shows them** — `finding.placed`, the same map the finder and the approvals
    inbox use.
  * **Making one is the workspace admin's**, because a form is a route
    strangers can reach that writes records.
  * **A form an app shipped is not ours to touch.**
"""

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/oneforms/service.py"
INSTALL = ROOT / "apps/oneapp/oneapp/install.py"
CATALOGUE = ROOT / "apps/oneapp/oneapp/catalogue.py"
MODULES = ROOT / "apps/oneapp/oneapp/modules.txt"
PAGE = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/Forms.vue"
WINDOW = ROOT / "apps/oneapp/frontend/src/modules/oneforms/components/FormsWindow.vue"
APP = ROOT / "apps/oneapp/frontend/src/App.vue"
ROUTER = ROOT / "apps/oneapp/frontend/src/router.js"
APPS = ROOT / "apps/oneapp/frontend/src/modules/onespace/lib/shell/apps.js"


@pytest.fixture
def forms(stub_frappe):
	from oneapp.oneforms import service

	return service


def _admin(forms, stub_frappe, yes=True):
	from oneapp.onespace.workspace import OWNER_ROLE

	stub_frappe.get_roles = lambda *a, **k: [OWNER_ROLE] if yes else ["Space-User"]


def _placed(forms, *doctypes):
	forms.finding.placed = lambda: {
		one: {"doctype": one, "space": "onehr", "space_label": "OnePeople",
		      "screen": "applicants", "label": one, "icon": "lucide-users",
		      "brand": "onehr", "fields": "", "filters": ""}
		for one in doctypes
	}


# ------------------------------------------------------------------ the rule

def test_only_a_doctype_one_of_your_spaces_shows_you(forms, stub_frappe):
	_admin(forms, stub_frappe)
	_placed(forms, "Job Applicant")
	assert [one["doctype"] for one in forms.offerable()] == ["Job Applicant"]

	with pytest.raises(Exception) as refused:
		forms._over("Salary Slip")
	assert "Salary Slip" in str(refused.value)


def test_making_one_over_something_you_cannot_see_is_refused(forms, stub_frappe):
	"""The failure this module exists to prevent.

	Publish a Web Form over Salary Slip and read it back, without ever holding
	a grant on Salary Slip. It is one line of manifest away from being possible
	and nothing else in the product would have stopped it.
	"""
	_admin(forms, stub_frappe)
	_placed(forms, "Job Applicant")
	with pytest.raises(Exception):
		forms.make("Salary Slip")


def test_the_offerable_list_is_the_same_map_the_finder_uses(forms):
	"""Not a list of its own, and the reason is drift.

	Three readings of "which doctypes are yours" disagree the first time a
	manifest moves a screen, and the one that disagrees silently is the one
	that decides what a stranger can write into.
	"""
	assert "finding.placed" in SOURCE.read_text()


# ----------------------------------------------------------------- the admin

def test_a_member_cannot_make_a_form(forms, stub_frappe):
	_admin(forms, stub_frappe, yes=False)
	for call in (forms.forms, lambda: forms.make("Job Applicant")):
		with pytest.raises(Exception) as refused:
			call()
		assert "admin" in str(refused.value).lower()


def test_every_endpoint_is_behind_the_admin_gate():
	"""Read off the tree: every whitelisted function calls `_admin` first.

	A gate that is on four doors out of five is not a gate, and this is the
	kind of thing that goes wrong when a sixth endpoint is added next month.
	"""
	tree = ast.parse(SOURCE.read_text())
	missed = []
	for node in ast.walk(tree):
		if not isinstance(node, ast.FunctionDef):
			continue
		if not any(isinstance(one, ast.Call) and "whitelist" in ast.unparse(one.func)
		           for one in node.decorator_list):
			continue
		called = {ast.unparse(inner.func) for inner in ast.walk(node)
		          if isinstance(inner, ast.Call)}
		if "_admin" not in called:
			missed.append(node.name)
	assert not missed, f"{missed} are whitelisted and do not check the reader"


def test_a_write_is_only_ever_after_the_check():
	"""`ignore_permissions` is how this writes, so the check is the whole of it.

	`Web Form` ships permissions for `Website Manager` and nobody in a
	workspace holds that — `alerts.py` reached the same place for the same
	reason. Which makes "did we check first" the only question worth guarding.
	"""
	source = SOURCE.read_text()
	assert "ignore_permissions=True" in source
	assert "OWNER_ROLE" in source and "SUPPORT_ROLE" in source


# ------------------------------------------------------------ somebody else's

def test_a_form_an_app_shipped_is_not_ours(forms, stub_frappe):
	_admin(forms, stub_frappe)

	class Theirs(dict):
		def get(self, key, default=None):
			return 0 if key == forms.OURS else super().get(key, default)

	forms.frappe.get_doc = lambda *a, **k: Theirs(name="contact")
	with pytest.raises(Exception) as refused:
		forms._ours("contact")
	assert "not made here" in str(refused.value)


def test_the_list_only_shows_forms_made_here(forms, stub_frappe):
	_admin(forms, stub_frappe)
	_placed(forms)
	asked = {}

	def get_all(doctype, **kwargs):
		asked.update(kwargs)
		return []

	forms.frappe.get_all = get_all
	forms.forms()
	assert asked["filters"] == {forms.OURS: 1}


def test_the_mark_is_written_on_the_way_in():
	assert '"Web Form": [' in INSTALL.read_text()
	assert 'custom_onespace' in INSTALL.read_text()


# ------------------------------------------------------------------ the route

def test_a_route_is_made_free_rather_than_refused(forms, stub_frappe):
	"""Two forms called "Contact us" is an ordinary thing for a workspace."""
	taken = {"contact-us"}
	forms.frappe.db.exists = lambda doctype, filters=None: (
		isinstance(filters, dict) and filters.get("route") in taken
	)
	forms.frappe.scrub = lambda value: str(value).lower().replace(" ", "_")
	assert forms._route("Contact us") == "contact-us-2"


def test_a_new_form_is_not_live(forms, stub_frappe):
	"""A URL somebody made by accident is a URL strangers can post to."""
	_admin(forms, stub_frappe)
	_placed(forms, "Job Applicant")
	written = {}

	class Doc(dict):
		name = "applicants"
		route = "job-applicant"
		title = "Job Applicant"

		def update(self, values):
			written.update(values)

		def insert(self, **kwargs):
			pass

	forms.frappe.new_doc = lambda doctype: Doc()
	forms.frappe.scrub = lambda value: str(value).lower().replace(" ", "_")
	forms.frappe.db.exists = lambda *a, **k: False
	forms.make("Job Applicant")
	assert written["published"] == 0
	assert written["login_required"] == 1
	assert written[forms.OURS] == 1


# ------------------------------------------------------------ a service, not a space

def test_it_is_declared_a_service():
	source = CATALOGUE.read_text()
	assert '_one("oneforms", SERVICE, module="OneForms")' in source
	assert '_one("oneforms", SERVICE, built=False)' not in source
	assert "OneForms" in MODULES.read_text()


def test_there_is_no_space_manifest_for_it():
	"""A form is not a department. `docs/CLEANUP.md` §1 is the distinction."""
	spaces = ROOT / "apps/oneapp_control/oneapp_control/spaces"
	assert not (spaces / "oneforms.py").exists()


def test_the_window_and_the_route_are_both_there():
	assert "<FormsWindow />" in APP.read_text()
	assert "name: 'Forms'" in ROUTER.read_text()
	assert "brand: 'oneforms'" in APPS.read_text()
	# And it is out of the drawn-and-not-built list at the foot of that file.
	assert "{ brand: 'oneforms' }," not in APPS.read_text()


def test_the_window_reads_its_name_rather_than_typing_it():
	"""`MARKS[id].name` is the only place a product name is written down.

	Comments are stripped first, and that is not a loophole: the rule is about
	what a *reader* sees. A comment explaining which app this is has to name
	it, and a guard that forbade that would be a guard that made the file
	harder to read in order to enforce a rule about strings.
	"""
	import re

	markup = re.sub(r"<!--.*?-->", "", WINDOW.read_text() + PAGE.read_text(),
	                flags=re.S)
	assert "nameOf('oneforms')" in markup
	assert "OneForms" not in markup.split("<script")[0]
