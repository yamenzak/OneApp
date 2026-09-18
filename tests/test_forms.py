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
BUILDER = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/FormBuilder.vue"
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


# ============================================================================ #
# Stages 3 to 6 — the page a stranger sees, the invitation, the list, the count
# ============================================================================ #

PUBLIC = ROOT / "apps/oneapp/oneapp/oneforms/public.py"
INVITE = ROOT / "apps/oneapp/oneapp/oneforms/invite.py"
PAGE_VUE = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/PublicForm.vue"


def _guest_endpoints(path):
	"""Every whitelisted function in a file, with how it was whitelisted."""
	found = {}
	for node in ast.walk(ast.parse(path.read_text())):
		if not isinstance(node, ast.FunctionDef):
			continue
		for one in node.decorator_list:
			if isinstance(one, ast.Call) and "whitelist" in ast.unparse(one.func):
				found[node.name] = ast.unparse(one)
	return found


def test_the_public_endpoints_let_a_guest_in_and_are_rate_limited():
	"""Both halves matter and they are the same sentence.

	A form nobody can reach without an account is not a public form; one
	anybody can hammer is a workspace's database as a service.
	"""
	source = PUBLIC.read_text()
	for name, decorator in _guest_endpoints(PUBLIC).items():
		assert "allow_guest=True" in decorator, f"{name} is the public page's"
	assert source.count("@rate_limit(") >= 2


def test_the_write_is_frappes_own_accept():
	"""A second answer to who may write what is the one thing that must not be.

	`accept` re-checks that the form is published, binds the request key to the
	docname, refuses a guest where a sign-in is required, and drops a signed-in
	session to Guest on an anonymous form. None of that is re-implemented here.
	"""
	source = PUBLIC.read_text()
	assert "from frappe.website.doctype.web_form.web_form import accept" in source
	tree = ast.parse(source)
	wrote = {ast.unparse(node.func) for node in ast.walk(tree)
	         if isinstance(node, ast.Call)}
	for forbidden in ("frappe.new_doc", "frappe.get_doc().insert", "doc.insert"):
		assert forbidden not in wrote, f"{forbidden} would make this a second write path"


def test_the_introduction_is_sanitised():
	"""Only an admin can set it and the page is served to strangers.

	So a script tag in it would run in *their* browser. `client_script` and
	`custom_css` are outside `SETTINGS` for the same reason — an admin's own
	rich text is not a licence to ship a visitor code.
	"""
	assert "sanitize_html" in PUBLIC.read_text()
	assert "v-html" in PAGE_VUE.read_text()


def test_every_reason_it_is_unavailable_reads_the_same():
	"""No such form, taken down, expired key, wrong key.

	Inside the product the two refusals are deliberately different sentences —
	`_refuse_ungranted` says why. Out here the difference between them is a
	fact about somebody's workspace that a stranger has no business being told.
	"""
	assert PUBLIC.read_text().count('_("This form is not available.")') == 2
	said = PAGE_VUE.read_text()
	assert said.count("This form is not available") == 1


def test_a_link_fields_options_are_resolved_on_the_server():
	"""`get_link_options` is not whitelisted, deliberately.

	It refuses a doctype Guest cannot read, refuses one no field of this form
	links to, and refuses a keyed form without its key. Three checks that only
	run if the call stays on the server.
	"""
	assert "get_link_options" in PUBLIC.read_text()
	assert "get_link_options" not in PAGE_VUE.read_text()


# ---------------------------------------------------------------- the invitation

def test_an_invitation_to_an_open_form_is_refused(forms, stub_frappe):
	"""A link anybody already had is not an invitation."""
	from oneapp.oneforms import invite as module

	class Open(dict):
		key_required = 0

	with pytest.raises(Exception) as refused:
		module._keyed(Open())
	assert "invitation" in str(refused.value).lower()


def test_taking_a_link_back_goes_through_the_same_gate():
	"""A request against a form this workspace did not make is refused too."""
	source = INVITE.read_text()
	assert "def uninvite" in source
	uninvite = source.split("def uninvite")[1].split("\ndef ")[0]
	assert "_ours(" in uninvite and "_admin()" in uninvite


def test_the_keyed_list_is_frappes_own_query():
	"""`get_web_form_list` filters to the key's own references before it runs.

	A second reading of which rows a key may see is exactly the thing that
	turns an invitation into a way to walk somebody's table.
	"""
	source = INVITE.read_text()
	assert "get_web_form_list" in source
	theirs = source.split("def theirs")[1]
	assert "frappe.get_all" not in theirs and "frappe.get_list" not in theirs


def test_deleting_a_form_takes_its_invitations_with_it():
	"""Frappe refuses to delete a document something links at, which is right.

	Here it also happens to be the behaviour somebody wants: the links stop
	working, which is what deleting the form was for.
	"""
	forget = SOURCE.read_text().split("def forget")[1].split("\n@")[0]
	assert "REQUEST" in forget and "delete_doc" in forget


# --------------------------------------------------------------- the list columns

def test_a_list_a_stranger_sees_names_its_columns(forms):
	"""Measured the first time `show_list` was turned on, and it threw.

	With no `list_columns`, Frappe falls back to the doctype's list-view fields
	and resolves every Link in them through
	`ensure_guest_key_link_doctype_allowed` — so a form over Job Applicant,
	whose `job_title` links to Job Opening, answered "You don't have permission
	to access the Job Opening DocType" to somebody holding a perfectly good
	key.
	"""
	source = SOURCE.read_text()
	assert "LINKISH" in source and "list_columns" in source
	assert "Link" in source.split("LINKISH")[1][:120]


# -------------------------------------------------------------- what a form knows

def test_a_form_does_not_claim_to_count_its_records(forms):
	"""Stage 6's finding rather than an omission.

	A Web Form writes an ordinary document and marks it in no way, so
	"responses to this form" is not a question the database can answer. Making
	it answerable means a column on every doctype a form is over — a schema
	change to somebody else's table, for a number the space's own list screen
	already shows.
	"""
	counted = SOURCE.read_text().split("def _counted")[1].split("\n@")[0]
	assert '"invited"' in counted and '"answered"' in counted
	assert '"responses"' not in counted
	# And the way to the real number: the doctype's own screen, placed the same
	# way everything else in this product is placed.
	assert '"place"' in counted and "finding.placed" in counted


# ------------------------------------------------------- the letter is a copy

def test_an_invitation_survives_a_workspace_with_no_outgoing_mail():
	"""Measured in the browser, on a dev site with no Email Account.

	`sendmail` threw, Frappe rolled the whole call back with it, and the key the
	press was *for* was lost over the delivery of a copy of it. The invitation
	is the link; the letter is a courtesy.
	"""
	source = (ROOT / "apps/oneapp/oneapp/oneforms/invite.py").read_text()
	sending = source.split("def _send")[1].split("\n@")[0]
	assert "try:" in sending and "except Exception:" in sending
	assert "log_error" in sending
	# And the answer says which happened, because "sent" and "made, now go and
	# send it" are different things to have done.
	assert '"mailed"' in source
	assert "mailed" in BUILDER.read_text()
