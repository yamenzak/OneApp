"""What people say *about* a file.

The notes inside a sheet are on its cells and are the workbook's own; this is
the other conversation, the one about the whole thing, and it is Frappe's
`Comment` on the `File` row rather than a store of ours.

Three claims are worth pinning, and the third is the one that decided the
storage.

**A reader may say something.** Somebody a workbook was shared with read-only
is exactly the person with a question about it, and refusing them the remark
leaves them nowhere to put it. So the gate is `read`, not `write`.

**An editor may not rewrite the conversation.** Being able to change a
workbook is not the same as being able to delete what somebody said about it:
a note is yours to remove and nobody else's, whatever they may do to the file.

**It is a `Comment`, so an `@` notifies.** `Comment.after_insert` calls
`notify_mentions` — the mention, the link back and the feed entry come for
nothing, and a store of ours would have meant writing all three worse.
"""

import importlib
import sys

import pytest


@pytest.fixture
def chatting(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp."):
			del sys.modules[name]
	return importlib.import_module("oneapp.onestorage.chatting"), stub_frappe


class _Doc:
	def __init__(self, name, may):
		self.name = name
		self.doctype = "File"
		self._may = may

	def check_permission(self, ptype="read"):
		import frappe
		if not self._may.get(ptype):
			frappe.throw("no", frappe.PermissionError)


def _a_file(frappe, **may):
	frappe.get_doc = lambda doctype, key=None: _Doc(key, may)


def test_a_reader_may_say_something(chatting):
	module, frappe = chatting
	_a_file(frappe, read=True)
	frappe.session.user = "robin@zzmock.test"

	written = {}

	def insert_doc(payload):
		written.update(payload)

		class Added:
			name = "COM-1"
			content = payload["content"]
			comment_email = payload["comment_email"]
			comment_by = payload["comment_by"]
			creation = "2026-09-10 12:00:00"

			def insert(self, **_):
				return self

		return Added()

	frappe.get_doc = lambda arg, key=None: (
		insert_doc(arg) if isinstance(arg, dict) else _Doc(key, {"read": True})
	)

	said = module.say("FILE-1", "  Are these March rates?  ")

	assert said["content"] == "Are these March rates?"
	assert said["mine"] is True
	# A `Comment` on the `File`, which is what makes the mention notify.
	assert written["doctype"] == "Comment"
	assert written["reference_doctype"] == "File"
	assert written["reference_name"] == "FILE-1"


def test_a_note_needs_something_in_it(chatting):
	module, frappe = chatting
	_a_file(frappe, read=True)
	with pytest.raises(Exception):
		module.say("FILE-1", "   ")


def test_somebody_who_cannot_open_it_says_nothing(chatting):
	module, frappe = chatting
	_a_file(frappe)
	with pytest.raises(Exception):
		module.say("FILE-1", "hello")
	with pytest.raises(Exception):
		module.notes("FILE-1")


def test_a_note_is_capped(chatting):
	module, frappe = chatting
	frappe.session.user = "robin@zzmock.test"

	kept = {}

	def insert_doc(payload):
		kept.update(payload)

		class Added:
			name = "COM-1"
			content = payload["content"]
			comment_email = payload["comment_email"]
			comment_by = payload["comment_by"]
			creation = "2026-09-10 12:00:00"

			def insert(self, **_):
				return self

		return Added()

	frappe.get_doc = lambda arg, key=None: (
		insert_doc(arg) if isinstance(arg, dict) else _Doc(key, {"read": True})
	)

	module.say("FILE-1", "x" * (module.MAX_CHARS + 500))
	assert len(kept["content"]) == module.MAX_CHARS


def test_only_your_own_note_is_yours_to_remove(chatting):
	module, frappe = chatting
	frappe.session.user = "robin@zzmock.test"

	class Row:
		reference_doctype = "File"
		reference_name = "FILE-1"
		comment_email = "someone.else@zzmock.test"

	frappe.get_doc = lambda arg, key=None: (
		Row() if arg == "Comment" else _Doc(key, {"read": True, "write": True})
	)

	# Write access to the file is not access to the conversation about it.
	with pytest.raises(Exception):
		module.unsay("COM-1")


def test_a_comment_on_something_else_is_not_reachable_here(chatting):
	module, frappe = chatting
	frappe.session.user = "robin@zzmock.test"

	class Row:
		reference_doctype = "Sales Invoice"
		reference_name = "ACC-SINV-0001"
		comment_email = "robin@zzmock.test"

	frappe.get_doc = lambda arg, key=None: (
		Row() if arg == "Comment" else _Doc(key, {"read": True})
	)

	# Otherwise this endpoint deletes comments off records, which is a
	# different permission and not one it checks.
	with pytest.raises(Exception):
		module.unsay("COM-1")


def test_the_conversation_comes_back_in_the_order_it_was_had(chatting):
	module, frappe = chatting
	_a_file(frappe, read=True)
	frappe.session.user = "robin@zzmock.test"

	asked = {}

	def get_all(doctype, **kwargs):
		asked.update(kwargs)
		return [{
			"name": "COM-1", "content": "first", "comment_email": "robin@zzmock.test",
			"comment_by": "Robin Vale", "creation": "2026-09-10 12:00:00",
		}]

	frappe.get_all = get_all
	frappe.db.count = lambda doctype, filters=None: 1

	answer = module.notes("FILE-1")

	# Oldest first: a feed reads newest-first and a conversation does not.
	assert asked["order_by"] == "creation asc"
	assert answer["notes"][0]["mine"] is True
	assert answer["count"] == 1
