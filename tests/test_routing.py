"""Rules that hand a record to somebody when it reaches a state.

Frappe's own `Assignment Rule`, through the same gate and the same vocabulary
as the alerts beside it — so what is worth testing here is the small set of
things routing does *differently*, and the first one is a bug that would
otherwise be silent.

**The condition is compiled bare.** `Notification` evaluates with the document
bound to the name `doc`; `Assignment Rule` passes the document as the eval's
*locals*. A `doc.`-prefixed test there is not an error — it is `False` for
ever, so the rule never fires and nothing says why.

**A rule must have a condition.** An alert with none fires on every save, which
is noisy. A handover with none assigns every record of that kind to somebody
for ever, which nobody means and nobody notices until a hundred tasks have
landed on one person.

**The people are the workspace's.** A rule that round-robins onto
Administrator is a rule that assigns work to us.
"""

import types

import pytest


@pytest.fixture
def routing(monkeypatch):
	from oneapp.onespace import routing as module

	monkeypatch.setattr(module.sync, "granted_doctypes",
	                    lambda: {"One Task", "Project"})
	monkeypatch.setattr(module, "users", lambda: [
		{"value": "ada@x.test", "label": "Ada"},
		{"value": "bo@x.test", "label": "Bo"},
	])
	return module


def meta(**fields):
	rows = [
		types.SimpleNamespace(fieldname=name, fieldtype=kind, label=name,
		                      options=option, hidden=0)
		for name, (kind, option) in fields.items()
	]
	return types.SimpleNamespace(
		fields=rows,
		is_submittable=0,
		get_field=lambda name: next((f for f in rows if f.fieldname == name), None),
	)


TASK = {"state": ("Select", ""), "owner_user": ("Link", "User")}


class Rule:
	"""Enough of an `Assignment Rule` to be written to."""

	def __init__(self):
		self.name = ""
		self.rows = {}
		self.children = {}
		self.saved = False

	def update(self, values):
		self.rows.update(values)

	def set(self, key, value):
		# Child rows come back off a real document as objects, which is how
		# `_read` walks them — so the fake stores them the same way and keeps
		# the dicts beside it for the assertions.
		self.rows[key] = value
		if isinstance(value, list) and value and isinstance(value[0], dict):
			self.children[key] = [types.SimpleNamespace(**row) for row in value]

	@property
	def users(self):
		return self.children.get("users", [])

	def get(self, key, default=None):
		return self.rows.get(key, default)

	def save(self, **kw):
		self.saved = True

	def __getattr__(self, key):
		return self.rows.get(key)


def writing(routing, monkeypatch, fields=None):
	rule = Rule()
	# `raising=False`: the stub only grows the attributes a module under test
	# reaches for, which is the same note `test_alerts.py` carries.
	monkeypatch.setattr(routing.frappe, "new_doc", lambda doctype: rule,
	                    raising=False)
	monkeypatch.setattr(routing.alerts, "_meta", lambda doctype: meta(**(fields or TASK)))
	return rule


# --------------------------------------------------------------------------- #
# The condition
# --------------------------------------------------------------------------- #

def test_the_condition_is_compiled_without_the_doc_prefix(routing, monkeypatch):
	"""The one that would be silent. `Assignment Rule` hands the document to
	`safe_eval` as its locals, so `doc.state` is a name that does not exist and
	the rule never fires."""
	rule = writing(routing, monkeypatch)
	routing.save({
		"title": "zzReview", "doctype": "One Task", "way": "in turn",
		"users": ["ada@x.test"],
		"condition": {"field": "state", "operator": "is", "value": "In review"},
	})
	assert rule.rows["assign_condition"] == 'state == "In review"'


def test_a_rule_with_no_condition_is_refused(routing, monkeypatch):
	"""It would assign every record of that kind, for ever."""
	writing(routing, monkeypatch)
	with pytest.raises(Exception):
		routing.save({
			"title": "zzEverything", "doctype": "One Task", "way": "in turn",
			"users": ["ada@x.test"], "condition": None,
		})


def test_a_condition_reads_back_as_the_triple_it_was_written_as(routing):
	from oneapp.onespace import alerts

	built = 'state == "In review"'
	assert alerts._decompile(built, alerts.BARE) == {
		"field": "state", "operator": "is", "value": "In review",
	}


# --------------------------------------------------------------------------- #
# Who it may hand work to
# --------------------------------------------------------------------------- #

def test_somebody_outside_the_workspace_is_dropped(routing, monkeypatch):
	"""Not refused — dropped, and refused only if nothing is left: a stale
	picker naming somebody who has since gone should not make the rule
	unsaveable, but it must not write them either."""
	rule = writing(routing, monkeypatch)
	routing.save({
		"title": "zzReview", "doctype": "One Task", "way": "in turn",
		"users": ["ada@x.test", "Administrator"],
		"condition": {"field": "state", "operator": "is", "value": "In review"},
	})
	assert rule.rows["users"] == [{"user": "ada@x.test"}]


def test_a_rule_with_nobody_left_is_refused(routing, monkeypatch):
	writing(routing, monkeypatch)
	with pytest.raises(Exception):
		routing.save({
			"title": "zzReview", "doctype": "One Task", "way": "in turn",
			"users": ["Administrator"],
			"condition": {"field": "state", "operator": "is", "value": "In review"},
		})


def test_a_doctype_the_workspace_does_not_have_is_refused(routing, monkeypatch):
	writing(routing, monkeypatch)
	with pytest.raises(Exception):
		routing.save({
			"title": "zzReview", "doctype": "Error Log", "way": "in turn",
			"users": ["ada@x.test"],
			"condition": {"field": "state", "operator": "is", "value": "x"},
		})


# --------------------------------------------------------------------------- #
# How it chooses
# --------------------------------------------------------------------------- #

def test_the_way_is_a_vocabulary_over_frappes_own(routing, monkeypatch):
	rule = writing(routing, monkeypatch)
	routing.save({
		"title": "zzReview", "doctype": "One Task", "way": "by load",
		"users": ["ada@x.test"],
		"condition": {"field": "state", "operator": "is", "value": "In review"},
	})
	assert rule.rows["rule"] == "Load Balancing"


def test_a_way_that_is_not_offered_is_refused(routing, monkeypatch):
	writing(routing, monkeypatch)
	with pytest.raises(Exception):
		routing.save({
			"title": "zzReview", "doctype": "One Task", "way": "by vibes",
			"users": ["ada@x.test"],
			"condition": {"field": "state", "operator": "is", "value": "x"},
		})


def test_assigning_by_a_field_needs_a_field_that_holds_a_person(routing, monkeypatch):
	rule = writing(routing, monkeypatch)
	routing.save({
		"title": "zzReview", "doctype": "One Task", "way": "by field",
		"field": "owner_user", "users": ["ada@x.test"],
		"condition": {"field": "state", "operator": "is", "value": "In review"},
	})
	assert rule.rows["field"] == "owner_user"

	with pytest.raises(Exception):
		routing.save({
			"title": "zzReview", "doctype": "One Task", "way": "by field",
			"field": "state", "users": ["ada@x.test"],
			"condition": {"field": "state", "operator": "is", "value": "In review"},
		})


def test_the_field_is_cleared_when_the_rule_does_not_read_one(routing, monkeypatch):
	"""Left behind, it is a field Frappe reads for a rule that is not about it."""
	rule = writing(routing, monkeypatch)
	routing.save({
		"title": "zzReview", "doctype": "One Task", "way": "in turn",
		"field": "owner_user", "users": ["ada@x.test"],
		"condition": {"field": "state", "operator": "is", "value": "In review"},
	})
	assert rule.rows["field"] is None


# --------------------------------------------------------------------------- #
# What it never writes
# --------------------------------------------------------------------------- #

def test_unassigning_is_never_written(routing, monkeypatch):
	"""Frappe will take an assignment away when a second condition goes true,
	and that is a footgun with a delay on it: work vanishes from somebody's
	list, on a rule written weeks ago, with nothing on the record to say why."""
	rule = writing(routing, monkeypatch)
	routing.save({
		"title": "zzReview", "doctype": "One Task", "way": "in turn",
		"users": ["ada@x.test"],
		"unassign_condition": "state == \"Done\"",
		"close_condition": "1",
		"condition": {"field": "state", "operator": "is", "value": "In review"},
	})
	assert rule.rows["unassign_condition"] == ""
	assert rule.rows["close_condition"] == ""


def test_every_day_is_written_so_a_rule_fires_at_all(routing, monkeypatch):
	"""Frappe skips a rule whose day table does not hold today, and an empty
	table is easy to read as "every day" and is not."""
	rule = writing(routing, monkeypatch)
	routing.save({
		"title": "zzReview", "doctype": "One Task", "way": "in turn",
		"users": ["ada@x.test"],
		"condition": {"field": "state", "operator": "is", "value": "In review"},
	})
	assert [row["day"] for row in rule.rows["assignment_days"]] == list(routing.DAYS)


def test_a_rule_somebody_else_made_is_not_ours_to_change(routing, monkeypatch):
	"""An app's own rule is exported to disk and written back over on the next
	deploy, so an edit here silently un-happens."""
	monkeypatch.setattr(routing.frappe, "get_doc",
	                    lambda doctype, name: types.SimpleNamespace(get=lambda key: None),
	                    raising=False)
	with pytest.raises(Exception):
		routing._ours("Some App Rule")
