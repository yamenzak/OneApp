"""The ladder, rung by rung.

Every test here is about a date comparison and what it is allowed to cause. The
ones that matter most are the refusals — this is the only part of the product
that destroys customer data, and it does so on a timer with nobody watching.
"""

import datetime

import pytest


@pytest.fixture
def sweep(stub_frappe, monkeypatch):
	from oneapp_control.lifecycle import sweep as module

	# Real date arithmetic. The stub's `add_to_date` and `today` answer None,
	# and a ladder tested against None passes by not comparing anything.
	fixed = datetime.date(2026, 6, 1)
	monkeypatch.setattr(module, "today", lambda: str(fixed))
	monkeypatch.setattr(module, "now_datetime", lambda: datetime.datetime(2026, 6, 1, 3, 0))

	def add_to_date(when, days=0, as_string=False):
		base = when if isinstance(when, datetime.date) else datetime.date.fromisoformat(str(when)[:10])
		out = base + datetime.timedelta(days=days)
		return str(out) if as_string else out

	monkeypatch.setattr(module, "add_to_date", add_to_date)
	monkeypatch.setattr(
		module,
		"getdate",
		lambda v=None: v if isinstance(v, datetime.date) and not isinstance(v, datetime.datetime)
		else (fixed if v is None else datetime.date.fromisoformat(str(v)[:10])),
	)
	return module


WINDOWS = {
	"dunning_grace_days": 7,
	"suspended_days": 14,
	"cold_retention_days": 60,
	"purge_warning_days": 7,
	"overage_grace_days": 7,
	"auto_purge_enabled": True,
}


class FakeTenant:
	def __init__(self, **kw):
		self.name = kw.pop("name", "acme")
		self.tenant_name = "Acme"
		self.owner_email = "owner@acme.test"
		self.status = "Active"
		self.subscription = "SUB-1"
		self.trial_ends_on = None
		self.lifecycle_hold = 0
		self.dunning_started_on = None
		self.dunning_stage = None
		self.suspended_on = None
		self.archived_on = None
		self.purge_after = None
		self.purge_warned_on = None
		self.cold_storage_key = None
		self.written = {}
		self.__dict__.update(kw)

	def get(self, key, default=None):
		return getattr(self, key, default)

	def db_set(self, field, value=None):
		values = field if isinstance(field, dict) else {field: value}
		self.written.update(values)
		for k, v in values.items():
			setattr(self, k, v)

	def reload(self):
		return self


class Recorder:
	"""Stands in for everything the rungs reach out to."""

	def __init__(self):
		self.jobs = []
		self.events = []
		self.emails = []
		self.purged = []
		self.cold = {"ok": True, "key": "cold/acme/x"}


@pytest.fixture
def wired(sweep, monkeypatch):
	rec = Recorder()

	monkeypatch.setattr(sweep.events, "record",
	                    lambda t, e, **k: rec.events.append((e, k)) or "TLE-1")
	monkeypatch.setattr(sweep.events, "opening",
	                    lambda t, e, **k: rec.events.append((e, k)) or "TLE-1")
	monkeypatch.setattr(sweep.events, "close", lambda *a, **k: None)
	monkeypatch.setattr(sweep.events, "last", lambda t, e: None)
	monkeypatch.setattr(sweep.cold, "ensure", lambda name, **k: rec.cold)
	monkeypatch.setattr(sweep.cold, "purge",
	                    lambda t, **k: rec.purged.append(t.name) or {"ok": True, "deleted": 7})
	# `start` reads the windows itself to work out the date it quotes in the
	# first email; the stub's settings singleton is None.
	monkeypatch.setattr(sweep.policy, "windows", lambda: WINDOWS)

	for name in ("payment_failed", "suspension_warning", "suspended", "archived",
	             "purge_warning", "purged", "restored", "nothing_to_restore"):
		# True, because a real send returns whether the mail actually went and
		# the ladder now reads that — see `_warn_about_purge`.
		monkeypatch.setattr(
			sweep.emails, name,
			lambda *a, _n=name, **k: rec.emails.append((_n, k)) or True,
		)

	import types

	runner = types.SimpleNamespace(
		enqueue=lambda tenant, action, payload=None, idempotency_key=None:
			rec.jobs.append((tenant, action, payload))
	)
	monkeypatch.setitem(
		__import__("sys").modules, "oneapp_control.provisioning.runner", runner
	)
	return rec


def _sub(monkeypatch, sweep, status):
	monkeypatch.setattr(sweep.frappe.db, "get_value", lambda *a, **k: status)


# --------------------------------------------------------------------------- #
# Getting on the ladder
# --------------------------------------------------------------------------- #

def test_a_paid_workspace_is_left_alone(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Active")
	tenant = FakeTenant()
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) is None
	assert wired.jobs == []


def test_an_unpaid_workspace_starts_the_clock_and_is_written_to(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Past Due")
	tenant = FakeTenant()
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "started dunning"
	assert tenant.dunning_started_on == "2026-06-01"
	assert [e for e, _ in wired.emails] == ["payment_failed"]
	assert wired.jobs == [], "nothing happens to the site on day one"


def test_a_workspace_an_operator_made_is_not_dunned(sweep, wired, monkeypatch):
	"""No subscription, no trial. An internal instance or a migration in
	progress — duning it would be automation surprising the person who built it.
	"""
	tenant = FakeTenant(subscription=None, trial_ends_on=None)
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) is None


def test_a_lapsed_trial_is_unpaid(sweep, wired, monkeypatch):
	tenant = FakeTenant(subscription=None, trial_ends_on="2026-05-01")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "started dunning"


def test_a_trial_still_running_is_paid(sweep, wired, monkeypatch):
	tenant = FakeTenant(subscription=None, trial_ends_on="2026-07-01")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) is None


def test_a_hold_freezes_a_workspace_out_of_all_of_it(sweep, wired, monkeypatch):
	"""A demo instance, a dispute, a legal hold."""
	_sub(monkeypatch, sweep, "Past Due")
	tenant = FakeTenant(
		lifecycle_hold=1, dunning_started_on="2026-01-01", status="Suspended",
		suspended_on="2026-01-08", purge_after="2026-02-01",
	)
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) is None
	assert wired.jobs == []
	assert wired.purged == []


# --------------------------------------------------------------------------- #
# Grace
# --------------------------------------------------------------------------- #

def test_nothing_happens_in_the_middle_of_grace(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Past Due")
	tenant = FakeTenant(dunning_started_on="2026-05-29")  # day 3 of 7
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) is None
	assert wired.emails == []


def test_the_second_warning_lands_two_days_out(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Past Due")
	tenant = FakeTenant(dunning_started_on="2026-05-27")  # day 5 of 7
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "warned"
	assert [e for e, _ in wired.emails] == ["suspension_warning"]


def test_the_second_warning_is_sent_once_per_fall(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Past Due")
	monkeypatch.setattr(
		sweep.events, "last", lambda t, e: {"occurred_on": "2026-05-30"}
	)
	tenant = FakeTenant(dunning_started_on="2026-05-27")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) is None


def test_a_warning_from_a_previous_fall_does_not_count(sweep, wired, monkeypatch):
	"""Somebody who recovered and failed again is warned again — the earlier
	warning was about a different lapse."""
	_sub(monkeypatch, sweep, "Past Due")
	monkeypatch.setattr(
		sweep.events, "last", lambda t, e: {"occurred_on": "2026-01-01"}
	)
	tenant = FakeTenant(dunning_started_on="2026-05-27")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "warned"


# --------------------------------------------------------------------------- #
# Suspension
# --------------------------------------------------------------------------- #

def test_grace_running_out_suspends_the_site(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Past Due")
	tenant = FakeTenant(dunning_started_on="2026-05-25")  # day 7 of 7
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "suspended"
	assert wired.jobs == [("acme", "Suspend Site", {"reason": "Payment overdue"})]
	assert [e for e, _ in wired.emails] == ["suspended"]


def test_the_cold_copy_is_taken_before_the_site_goes_off(sweep, wired, monkeypatch):
	"""A deactivated site is in maintenance mode, and Frappe's scheduler refuses
	to run at all under maintenance mode. After suspension it can never make one.
	"""
	_sub(monkeypatch, sweep, "Past Due")
	order = []
	monkeypatch.setattr(sweep.cold, "ensure",
	                    lambda n, **k: order.append("cold") or {"ok": True})

	import types
	monkeypatch.setitem(
		__import__("sys").modules, "oneapp_control.provisioning.runner",
		types.SimpleNamespace(enqueue=lambda *a, **k: order.append("suspend")),
	)
	tenant = FakeTenant(dunning_started_on="2026-05-25")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	sweep.consider("acme", WINDOWS)
	assert order == ["cold", "suspend"]


def test_suspension_waits_while_a_final_backup_is_still_coming(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Past Due")
	wired.cold = {"ok": False, "reason": "requested"}
	tenant = FakeTenant(dunning_started_on="2026-05-25")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "waiting for a final backup"
	assert wired.jobs == []


def test_a_workspace_with_no_backup_at_all_is_still_suspended(sweep, wired, monkeypatch):
	"""Suspension is reversible. It is archiving that needs the copy."""
	_sub(monkeypatch, sweep, "Past Due")
	wired.cold = {"ok": False, "reason": "no_backup"}
	tenant = FakeTenant(dunning_started_on="2026-05-25")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "suspended"


# --------------------------------------------------------------------------- #
# Archiving
# --------------------------------------------------------------------------- #

def test_a_suspended_workspace_is_archived_once_its_window_runs_out(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Past Due")
	tenant = FakeTenant(
		status="Suspended", dunning_started_on="2026-05-01",
		suspended_on="2026-05-10", cold_storage_key="cold/acme/x",
	)
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "archiving"
	assert wired.jobs[0][1] == "Archive Site"
	assert tenant.purge_after == "2026-07-31", "sixty days from today"


def test_a_suspended_workspace_inside_its_window_is_left_alone(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Past Due")
	tenant = FakeTenant(
		status="Suspended", dunning_started_on="2026-05-20", suspended_on="2026-05-28",
	)
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) is None


def test_archiving_refuses_without_a_cold_copy(sweep, wired, monkeypatch):
	"""The site is deleted at this rung. No copy means archiving destroys the
	workspace, so it stays suspended and an operator is told."""
	_sub(monkeypatch, sweep, "Past Due")
	wired.cold = {"ok": False, "reason": "no_backup"}
	tenant = FakeTenant(
		status="Suspended", dunning_started_on="2026-05-01",
		suspended_on="2026-05-10", cold_storage_key=None,
	)
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "refused to archive without a cold copy"
	assert wired.jobs == []
	assert tenant.status == "Suspended"


def test_a_workspace_an_operator_suspended_by_hand_is_not_archived(sweep, wired, monkeypatch):
	"""No clock, so it is not on the ladder. Automation must not finish a
	human's half-finished action."""
	_sub(monkeypatch, sweep, "Active")
	tenant = FakeTenant(status="Suspended", dunning_started_on=None,
	                    suspended_on="2026-01-01")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) is None
	assert wired.jobs == []


# --------------------------------------------------------------------------- #
# Purging
# --------------------------------------------------------------------------- #

def test_an_archived_workspace_is_warned_before_the_purge(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Canceled")
	tenant = FakeTenant(status="Archived", dunning_started_on="2026-01-01",
	                    purge_after="2026-06-05", cold_storage_key="cold/acme/x")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "warned about the purge"
	assert [e for e, _ in wired.emails] == ["purge_warning"]
	assert tenant.purge_warned_on == "2026-06-01"


def test_the_purge_runs_once_the_date_and_the_warning_are_both_behind_us(
	sweep, wired, monkeypatch
):
	_sub(monkeypatch, sweep, "Canceled")
	tenant = FakeTenant(status="Archived", dunning_started_on="2026-01-01",
	                    purge_after="2026-05-31", purge_warned_on="2026-05-01")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "purged (7 objects)"
	assert wired.purged == ["acme"]
	assert tenant.status == "Purged"


def test_the_purge_refuses_on_a_workspace_that_was_never_warned(sweep, wired, monkeypatch):
	"""A window widened and then narrowed, or a sweep that did not run. Warn
	now; purge on a later pass."""
	_sub(monkeypatch, sweep, "Canceled")
	tenant = FakeTenant(status="Archived", dunning_started_on="2026-01-01",
	                    purge_after="2026-05-01", purge_warned_on=None)
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "warned about the purge"
	assert wired.purged == []


def test_the_purge_refuses_while_the_warning_is_still_fresh(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Canceled")
	tenant = FakeTenant(status="Archived", dunning_started_on="2026-01-01",
	                    purge_after="2026-05-31", purge_warned_on="2026-05-30")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) is None
	assert wired.purged == []


def test_the_purge_refuses_when_the_switch_is_off(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Canceled")
	tenant = FakeTenant(status="Archived", dunning_started_on="2026-01-01",
	                    purge_after="2026-05-01", purge_warned_on="2026-04-01")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", {**WINDOWS, "auto_purge_enabled": False}) is None
	assert wired.purged == []


def test_a_workspace_archived_by_hand_is_never_purged(sweep, wired, monkeypatch):
	"""No purge date. An operator who wants it destroyed sets one; automation
	does not decide that for them."""
	_sub(monkeypatch, sweep, "Canceled")
	tenant = FakeTenant(status="Archived", dunning_started_on=None, purge_after=None)
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) is None
	assert wired.purged == []


# --------------------------------------------------------------------------- #
# Coming back
# --------------------------------------------------------------------------- #

def test_paying_while_suspended_resumes_the_site(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Active")
	tenant = FakeTenant(status="Suspended", dunning_started_on="2026-05-01",
	                    suspended_on="2026-05-10")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "resuming"
	assert wired.jobs[0][1] == "Resume Site"
	assert tenant.dunning_started_on is None


def test_paying_while_archived_restores_from_the_cold_copy(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Active")
	tenant = FakeTenant(status="Archived", dunning_started_on="2026-01-01",
	                    purge_after="2026-07-01", cold_storage_key="cold/acme/x")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "restoring"
	assert wired.jobs[0][1] == "Restore Site"
	assert tenant.purge_after is None, "a paying workspace must not sit on a timer"


def test_paying_after_the_purge_says_so_rather_than_restoring_nothing(
	sweep, wired, monkeypatch
):
	"""A restore with no copy produces an empty workspace and looks like it
	worked, which is worse than saying there is nothing left."""
	_sub(monkeypatch, sweep, "Active")
	tenant = FakeTenant(status="Archived", dunning_started_on="2026-01-01",
	                    cold_storage_key=None)
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "recovered, but there is nothing to restore"
	assert [e for e, _ in wired.emails] == ["nothing_to_restore"]
	assert wired.jobs == []


def test_recovering_clears_the_whole_clock(sweep, wired, monkeypatch):
	_sub(monkeypatch, sweep, "Active")
	tenant = FakeTenant(status="Active", dunning_started_on="2026-05-01",
	                    dunning_stage="Grace", purge_after="2026-07-01",
	                    purge_warned_on="2026-06-01")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "cleared"
	assert tenant.dunning_started_on is None
	assert tenant.dunning_stage is None
	assert tenant.purge_after is None
	assert tenant.purge_warned_on is None


# --------------------------------------------------------------------------- #
# The warning has to have actually been sent
# --------------------------------------------------------------------------- #
# `purge_warned_on` is the gate in front of the only irreversible step in the
# product. A gate satisfied by an email nobody received is not a gate — it is a
# record of us having meant to.

def test_a_warning_that_could_not_be_sent_does_not_count(sweep, wired, monkeypatch):
	"""A control plane with no outgoing Email Account would otherwise mark every
	workspace as warned and destroy them all on schedule, silently."""
	_sub(monkeypatch, sweep, "Canceled")
	monkeypatch.setattr(sweep.emails, "purge_warning", lambda *a, **k: False)

	tenant = FakeTenant(status="Archived", dunning_started_on="2026-01-01",
	                    purge_after="2026-06-05", cold_storage_key="cold/acme/x")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "could not warn them; the purge is on hold"
	assert tenant.purge_warned_on is None
	assert wired.purged == []


def test_an_unsendable_warning_holds_the_purge_open_indefinitely(sweep, wired, monkeypatch):
	"""Past the date, past the window, and still not purged — because nobody was
	told. The workspace waits for an operator rather than for a timer."""
	_sub(monkeypatch, sweep, "Canceled")
	monkeypatch.setattr(sweep.emails, "purge_warning", lambda *a, **k: False)

	tenant = FakeTenant(status="Archived", dunning_started_on="2026-01-01",
	                    purge_after="2026-01-01", purge_warned_on=None)
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)

	assert sweep.consider("acme", WINDOWS) == "could not warn them; the purge is on hold"
	assert wired.purged == []


def test_the_event_log_records_whether_they_were_actually_told(sweep, wired, monkeypatch):
	"""A year later, in a dispute, "we warned them" has to be checkable."""
	_sub(monkeypatch, sweep, "Canceled")
	monkeypatch.setattr(sweep.emails, "purge_warning", lambda *a, **k: False)

	tenant = FakeTenant(status="Archived", dunning_started_on="2026-01-01",
	                    purge_after="2026-06-05")
	monkeypatch.setattr(sweep.frappe, "get_doc", lambda *a: tenant)
	sweep.consider("acme", WINDOWS)

	warned = [kwargs for event, kwargs in wired.events if event == "Purge Warned"]
	assert warned and warned[0]["detail"] == {"delivered": False}


# --------------------------------------------------------------------------- #
# The rehearsal clock
# --------------------------------------------------------------------------- #
# The windows have floors, so the shortest honest walk to a purge is about nine
# days. A rehearsal moves the calendar instead of the rules — and must never be
# pointable at somebody's live business.

def test_the_rehearsal_clock_refuses_a_production_workspace(stub_frappe, monkeypatch):
	"""The one thing this must never do."""
	from oneapp_control.api import admin

	monkeypatch.setattr(admin.frappe, "get_roles", lambda *a: ["System Manager"])
	tenant = type("T", (), {
		"environment": "Production", "name": "acme", "lifecycle_hold": 0,
		"get": lambda self, f, d=None: None, "db_set": lambda self, *a: None,
	})()
	monkeypatch.setattr(admin.frappe, "get_doc", lambda *a: tenant)

	with pytest.raises(Exception, match="Production"):
		admin.advance_lifecycle_clock("acme", 30)


def test_the_rehearsal_clock_refuses_a_backwards_number(stub_frappe, monkeypatch):
	from oneapp_control.api import admin

	monkeypatch.setattr(admin.frappe, "get_roles", lambda *a: ["System Manager"])
	for days in (0, -5):
		with pytest.raises(Exception):
			admin.advance_lifecycle_clock("acme", days)


def test_every_lifecycle_date_moves_together(stub_frappe):
	"""A clock that moved some dates and not others would put a workspace into
	a state the ladder can never produce, and the rehearsal would be testing
	something that cannot happen."""
	import json
	from pathlib import Path

	from oneapp_control.api.admin import LIFECYCLE_DATES

	root = Path(__file__).resolve().parent.parent
	fields = {
		f["fieldname"]: f
		for f in json.loads(
			(root / "apps/oneapp_control/oneapp_control/control_plane/doctype"
			        "/tenant/tenant.json").read_text()
		)["fields"]
	}

	dated = {
		name
		for name, f in fields.items()
		if f["fieldtype"] in ("Date", "Datetime")
		and name not in ("provisioned_on", "purged_on", "restored_on", "usage_synced_on")
	}

	assert set(LIFECYCLE_DATES) == dated, (
		"the rehearsal clock and the Tenant's own dates disagree: "
		f"missing {dated - set(LIFECYCLE_DATES)}, "
		f"unknown {set(LIFECYCLE_DATES) - dated}"
	)
