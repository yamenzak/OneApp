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
import re

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

	made = []
	forms.frappe.new_doc = lambda doctype: Doc()
	forms.frappe.get_doc = lambda values: made.append(values) or Doc()
	forms.frappe.scrub = lambda value: str(value).lower().replace(" ", "_")
	forms.frappe.db.exists = lambda *a, **k: False
	forms.make("Job Applicant")
	assert written["published"] == 0
	assert written["login_required"] == 1
	assert written[forms.OURS] == 1

	# And the column that lets it say what it collected, on the doctype it is
	# over — added here rather than at install, because which doctypes a
	# workspace makes forms over is not knowable until it does.
	[column] = [one for one in made if one.get("doctype") == "Custom Field"]
	assert column["dt"] == "Job Applicant"
	assert column["fieldname"] == "custom_web_form"
	assert column["hidden"] and column["read_only"] and column["search_index"]


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


ATTACHING = ROOT / "apps/oneapp/oneapp/oneforms/attaching.py"


def test_the_one_write_that_is_not_accept_can_only_reach_what_accept_made():
	"""`attaching.py` is the exception and it is a narrow one.

	It exists because `accept` writes the `File` as the current user and on a
	public form that user is Guest, who cannot create one — `File` grants create
	to `All` and Guest is not in `All`. Measured in the browser, after the
	submission had already saved.

	What makes it safe is not the `ignore_permissions` being small: it is that
	the document it attaches to is the one `accept` returned. A name out of the
	payload would be a second answer to who may write what.
	"""
	tree = ast.parse(ATTACHING.read_text())
	onto = next(node for node in ast.walk(tree)
	            if isinstance(node, ast.FunctionDef) and node.name == "onto")
	body = ast.unparse(onto)

	assert "made.doctype" in body and "made.name" in body
	# Never a lookup, which is the only way a posted name could get in.
	for reaching in ("frappe.get_all", "frappe.get_list", "frappe.db.exists",
	                 'frappe.get_doc(made', "frappe.db.get_value("):
		assert reaching not in body.replace("frappe.db.set_value(", "")


def test_the_size_cap_is_the_servers_rather_than_the_browsers():
	"""Until this, nothing on the server looked at it at all: the page checked
	before reading, and anybody posting straight to `send` could put half a
	gigabyte of base64 in a string."""
	source = ATTACHING.read_text()
	decoded = source.split("def _decoded")[1]
	# Refused from the base64 length before the decode, and again after.
	assert decoded.index("len(payload)") < decoded.index("b64decode")
	assert "len(raw) > cap" in decoded


def test_what_somebody_attached_is_private():
	"""A CV at a guessable URL is a data leak, and `accept` does not set it."""
	assert '"is_private": 1' in ATTACHING.read_text()


def test_a_filename_from_a_stranger_is_scrubbed():
	"""It becomes a name on disk and a header."""
	decoded = ATTACHING.read_text().split("def _decoded")[1]
	assert 'rsplit("/", 1)' in decoded and "re.sub" in decoded


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

def test_a_form_says_what_it_collected(forms):
	"""Stage 6 said this was not a question the database could answer, because
	a Web Form writes an ordinary document and marks it in no way. That was
	right about the fact and wrong about what followed: the fix is one hidden
	column on the doctype the form is over, which is what every space in this
	product already does to somebody else's schema.
	"""
	counted = SOURCE.read_text().split("def _counted")[1].split("\n@")[0]
	assert '"responses"' in counted and "counting.how_many" in counted
	assert '"invited"' in counted and '"answered"' in counted


def test_the_way_through_is_the_screen_rather_than_a_table_of_our_own(forms):
	"""`finding.placed` already says which screen owns the doctype and
	`narrowing.js` already says how a URL asks one for a filter — so what came
	in is the list somebody already knows, with its views and its actions."""
	from oneapp.oneforms import counting

	target = {"space": "onehr", "screen": "applicants"}
	assert counting.where(target, "apply") == (
		"/one/space/onehr?screen=applicants&narrow=custom_web_form:apply")
	# And nothing at all where the doctype has no screen, rather than a link
	# into a page that does not exist.
	assert counting.where({}, "apply") == ""
	assert counting.where(target, "") == ""


def test_the_browser_builds_the_same_link_the_server_does():
	"""Two spellings of one URL is one that goes stale. The count on the list
	is a router push, so the column name is named on both sides — and if they
	ever disagree this is what says so."""
	from oneapp.oneforms import counting

	page = (ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/Forms.vue").read_text()
	assert f"const MARK = '{counting.MARK}'" in page
	assert "NARROW" in page


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


# ---------------------------------------------------------------- the layout

LAYOUT = ROOT / "apps/oneapp/frontend/src/modules/oneforms/lib/layout.js"
PUBLIC_PAGE = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/PublicForm.vue"


def test_a_page_break_is_offered_and_goes_in_nameless(forms):
	"""Frappe's `validate_fields` checks every *named* row against the doctype,
	and `Page Break` is not in its `no_value_fields` — so a page break called
	`page_break_5` is refused as a missing field. Measured by the seeder."""
	from frappe.model import no_value_fields

	assert "Page Break" in forms.BREAKS
	assert "Page Break" not in no_value_fields
	source = SOURCE.read_text()
	assert "no_value_fields" in source.split("def layout")[1].split("\n@")[0]


def test_a_doctypes_own_furniture_is_never_a_field_on_a_form(forms):
	"""A doctype's section break is where *its* designer wanted a heading, and
	a form is a different page."""
	assert {"Section Break", "Column Break", "Page Break"} <= forms.NEVER


def test_the_page_reads_the_rows_rather_than_drawing_them_flat():
	"""Stage 3 drew the list straight down, which is what the rows literally
	are and not what they mean — a Column Break fell through to the text-box
	branch and drew a nameless empty control."""
	page = PUBLIC_PAGE.read_text()
	assert "pagesOf" in page and "form-progress" in page
	assert "form-next" in page and "form-back" in page
	# And no branch on a break fieldtype, which is what flat looked like.
	assert "'Section Break'" not in page and "'Column Break'" not in page


def test_the_layout_is_its_own_function_with_its_own_tests():
	"""A break before any field, two in a row, a trailing one. A builder
	produces all three constantly and each is a way to draw an empty box."""
	assert LAYOUT.exists()
	assert (LAYOUT.parent / "layout.test.js").exists()


# ------------------------------------------------------------------ the file

FILE_FIELD = ROOT / "apps/oneapp/frontend/src/modules/oneforms/components/FileField.vue"


def test_a_form_can_take_a_file_without_a_second_way_to_write():
	"""`accept` reads `filename,data:…;base64,…`, writes the `File` itself and
	puts its url on the document. So there is no upload endpoint here and no
	guest upload permission — the one thing a public page must not be given is
	a second way to write, and `test_the_write_is_frappes_own_accept` is the
	guard that says so."""
	drawn = FILE_FIELD.read_text()
	assert "readAsDataURL" in drawn
	assert "${file.name},${reader.result}" in drawn
	# Nothing posted from here. Read off the code rather than the file, because
	# the comment above the control names the endpoint it is avoiding — the
	# third time in this module a grep-based guard matched its own prose.
	code = re.sub(r"<!--.*?-->|/\*.*?\*/|//[^\n]*", "", drawn, flags=re.S)
	for reaching in ("callMethod", "fetch(", "XMLHttpRequest", "upload_file"):
		assert reaching not in code


def test_the_cap_is_checked_before_the_file_is_read():
	"""Base64 is a third larger than the file and it rides in one POST, so
	reading a 200MB file into a string in order to then refuse it is how a tab
	stops responding."""
	drawn = FILE_FIELD.read_text()
	body = drawn.split("function take")[1]
	assert body.index("file.size > cap") < body.index("readAsDataURL")


def test_the_page_is_told_what_a_file_may_weigh():
	"""Said rather than discovered: a page that only finds out in a 413 is a
	page that lost somebody's upload."""
	assert '"max_attachment_size"' in (ROOT / "apps/oneapp/oneapp/oneforms/public.py").read_text()
	assert "max_attachment_size" in BUILDER.read_text()


def test_an_attach_field_is_offerable(forms):
	"""It never was in `NEVER`, which is why stage 3 let somebody drag one on
	and then handed a stranger a text box."""
	assert "Attach" not in forms.NEVER and "Attach Image" not in forms.NEVER
	assert "ATTACHES" in PUBLIC_PAGE.read_text()


# ------------------------------------------------------ the list a key holder sees

def test_which_columns_a_key_holder_sees_is_a_choice(forms):
	"""Stage 5 picked the first few for everybody, which is right as a fallback
	and wrong as the only answer: a supplier's list of their own orders should
	show what the workspace thinks matters."""
	class Row(dict):
		def __getattr__(self, name):
			return self.get(name)

	class Doc:
		web_form_fields = [
			Row(fieldname="name1", fieldtype="Data", label="Name"),
			Row(fieldname="email", fieldtype="Data", label="Email"),
			Row(fieldname="opening", fieldtype="Link", label="Opening"),
			Row(fieldname="note", fieldtype="Text", label="Note"),
			Row(fieldtype="Section Break", fieldname="", label=""),
			Row(fieldname="phone", fieldtype="Data", label="Phone"),
		]

	# Chosen, in the order they were chosen.
	assert [one["fieldname"] for one in forms._columns(Doc(), ["note", "name1"])] == \
		["note", "name1"]

	# A Link is never offered — it resolves against Guest and throws.
	assert [one["fieldname"] for one in forms._columns(Doc(), ["opening", "email"])] == \
		["email"]

	# Nothing chosen falls back, because empty is not "the default" — empty is
	# what makes Frappe resolve the doctype's own list-view Links against Guest.
	assert [one["fieldname"] for one in forms._columns(Doc(), None)] == \
		["name1", "email", "note", "phone"]
	assert [one["fieldname"] for one in forms._columns(Doc(), [])] == \
		["name1", "email", "note", "phone"]

	# And never more than fit on a phone.
	assert len(forms._columns(Doc(), ["name1", "email", "note", "phone"])) <= forms.LIST_COLUMNS


def test_a_column_that_is_no_longer_on_the_form_is_dropped_rather_than_refused(forms):
	"""A column list is a preference, and a form whose fields moved should
	still save."""
	class Row(dict):
		def __getattr__(self, name):
			return self.get(name)

	class Doc:
		web_form_fields = [Row(fieldname="email", fieldtype="Data", label="Email")]

	assert [one["fieldname"] for one in forms._columns(Doc(), ["gone", "email"])] == ["email"]


def test_the_builder_offers_the_choice_where_the_list_is_on():
	assert 'data-slot="builder-columns"' in BUILDER.read_text()
	assert '"columnable"' in SOURCE.read_text()


def test_the_palette_does_not_offer_what_nobody_could_fill_in(forms, stub_frappe):
	"""Caught in the builder after stage 12: `custom_web_form` is this module's
	own provenance column and it appeared in the palette as "Web Form". A form
	asking a stranger which form made it has lost the plot — and the same is
	true of anything the doctype hides or makes read-only."""
	import types

	from oneapp.oneforms import counting

	def field(fieldname, **kw):
		return types.SimpleNamespace(
			fieldname=fieldname, label=fieldname, fieldtype="Data", reqd=0,
			options="", hidden=kw.get("hidden", 0), read_only=kw.get("read_only", 0))

	stub_frappe.get_meta = lambda doctype: types.SimpleNamespace(fields=[
		field("applicant_name"),
		field(counting.MARK),
		field("secret", hidden=1),
		field("computed", read_only=1),
	])

	assert [one["fieldname"] for one in forms.available("Job Applicant")] == \
		["applicant_name"]


# ------------------------------------------------------------------ sharing it

def test_a_forms_link_can_be_taken_out_of_the_product():
	"""It was a caption. For a form that is open or sign-in-only there is no
	invitation panel, so the only way to get the URL was to read it off the
	screen and type it — and a form nobody can send is a form nobody fills in.
	"""
	builder = BUILDER.read_text()
	assert 'data-slot="builder-link"' in builder
	assert "/one/f/${page.route}" in builder


def test_an_invitation_can_pre_fill_and_can_be_bound_to_a_record():
	"""`Web Form Request.web_form_values` and its `references` have carried
	both since Frappe shipped them, and the builder posted `{}` and `''`: a
	supplier asked to confirm an address they have already given is a supplier
	typing it again."""
	builder = BUILDER.read_text()
	assert 'data-slot="builder-prefill"' in builder
	assert 'data-slot="builder-about"' in builder
	# Sent, rather than drawn and dropped.
	assert "prefilled(prefilling.value), about.value" in builder


def test_a_pre_fill_line_without_a_separator_is_skipped_rather_than_refused():
	"""It is a box somebody types into. The server checks the fieldnames
	against the form and is the one that gets to say no."""
	builder = BUILDER.read_text()
	body = builder.split("const prefilled")[1].split("\n}")[0]
	assert "[:=]" in body and "continue" in body
