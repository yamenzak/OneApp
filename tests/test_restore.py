"""Going back to a backup, and the bucket that has to be made to agree.

The half of a restore nobody builds is the second one. Frappe Cloud will put
the database back to Tuesday perfectly well; what it cannot know is that this
product keeps attachments as objects rather than as rows, so a record restored
away leaves its file in the bucket, referenced by nothing, invisible to every
screen and billed for every month from then on.

So these are about the two directions of that disagreement — objects no row
claims, and rows whose object is gone — and about the three refusals that stand
between a reconcile and deleting somebody's files for a reason that turns out to
have been a broken database.
"""

import datetime

import pytest


@pytest.fixture
def restore(stub_frappe):
	from oneapp.onespace import restore as module

	return module


@pytest.fixture
def backup(stub_frappe):
	from oneapp.onespace import backup as module

	return module


class FakeR2:
	"""The bucket, as the two functions here see it."""

	def __init__(self, objects=None, configured=True):
		self.objects = objects or []
		self.configured = configured
		self.deleted = []

	def is_configured(self):
		return self.configured

	def list_objects(self, prefix):
		return [row for row in self.objects if row["key"].startswith(prefix)]

	def delete_keys(self, keys):
		self.deleted.extend(keys)
		return len(keys)


def _object(key, size=100, minutes_old=120):
	return {
		"key": key,
		"size": size,
		"modified": datetime.datetime(2026, 6, 1, 12, 0, 0)
		- datetime.timedelta(minutes=minutes_old),
	}


@pytest.fixture
def bucket(restore, stub_frappe, monkeypatch):
	"""A workspace with a tenant name and a bucket, at a fixed moment."""
	stub_frappe.conf = {"oneapp_tenant": "acme"}
	monkeypatch.setattr(
		restore, "now_datetime", lambda: datetime.datetime(2026, 6, 1, 12, 0, 0)
	)

	def install(objects, known):
		fake = FakeR2(objects)
		monkeypatch.setattr(restore, "r2", fake)
		monkeypatch.setattr(restore, "known_keys", lambda: set(known))
		return fake

	return install


# --------------------------------------------------------------------------- #
# What the bucket keeps, and what it loses
# --------------------------------------------------------------------------- #

def test_an_object_no_row_claims_is_deleted(restore, bucket):
	"""The whole point. A file uploaded after the backup is restored away with
	the record that held it, and its bytes would otherwise sit there forever."""
	fake = bucket(
		[
			_object("tenants/acme/private/FILE-1/invoice.pdf"),
			_object("tenants/acme/private/FILE-2/orphan.pdf", size=4096),
		],
		known={"tenants/acme/private/FILE-1/invoice.pdf"},
	)

	result = restore.reconcile()

	assert result["deleted"] == 1
	assert fake.deleted == ["tenants/acme/private/FILE-2/orphan.pdf"]
	assert result["bytes"] == 4096
	assert result["kept"] == 1


def test_a_dry_run_says_what_it_would_take_and_takes_nothing(restore, bucket):
	fake = bucket(
		[_object("tenants/acme/private/FILE-2/orphan.pdf", size=10)],
		known={"tenants/acme/public/FILE-9/logo.png"},
	)

	result = restore.reconcile(dry_run=1)

	assert result["orphans"] == 1 and result["bytes"] == 10
	assert result["deleted"] == 0 and fake.deleted == []


def test_an_object_written_a_minute_ago_is_left_alone(restore, bucket):
	"""A direct upload writes the object first and the row second.

	Without a settling window the sweep eventually deletes a file somebody is
	in the middle of uploading — the one failure that would be indistinguishable
	from the product losing data at random.
	"""
	fake = bucket(
		[_object("tenants/acme/private/FILE-3/uploading.zip", minutes_old=1)],
		known={"tenants/acme/private/FILE-1/invoice.pdf"},
	)

	result = restore.reconcile()

	assert fake.deleted == []
	assert result["too_new"] == 1 and result["orphans"] == 0


def test_a_database_claiming_nothing_at_all_is_refused(restore, bucket):
	"""Not a workspace with no files. A workspace with no files has no objects.

	A bucket full of objects and a `File` table that claims none of them is a
	database that is mid-restore, half-migrated or broken, and deleting on its
	word is the worst thing this code could do.
	"""
	fake = bucket([_object(f"tenants/acme/private/FILE-{n}/x.pdf") for n in range(5)],
	              known=set())

	result = restore.reconcile()

	assert result["ok"] is False and result["reason"] == "nothing_claimed"
	assert fake.deleted == []


def test_rows_whose_object_is_gone_are_counted_and_not_hidden(restore, bucket):
	"""The other direction, which no restore can fix.

	A file deleted since the backup comes back as a row, because the row is in
	the dump. Its bytes went when the bin was emptied. The row will be there and
	the file will not open, and saying so is the only honest thing available.
	"""
	bucket(
		[_object("tenants/acme/private/FILE-1/invoice.pdf")],
		known={
			"tenants/acme/private/FILE-1/invoice.pdf",
			"tenants/acme/private/FILE-7/deleted-last-week.pdf",
		},
	)

	assert restore.reconcile()["missing"] == 1


def test_a_workspace_with_no_bucket_reconciles_nothing(restore, stub_frappe, monkeypatch):
	monkeypatch.setattr(restore, "r2", FakeR2(configured=False))
	assert restore.reconcile() == {"ok": False, "reason": "no_storage"}


# --------------------------------------------------------------------------- #
# Being told a restore happened
# --------------------------------------------------------------------------- #

class FakeState:
	def __init__(self, reconciled_for=None):
		self.files_reconciled_for = reconciled_for
		self.writes = []

	def db_set(self, field, value):
		self.writes.append((field, value))
		setattr(self, field, value)


def test_a_restore_is_noticed_and_reconciled_once(restore, stub_frappe, monkeypatch):
	"""The site's copy of the timestamp came out of the dump, so it is always
	older than a restore that has just happened. That is the whole mechanism."""
	state = FakeState(reconciled_for="2026-05-01 09:00:00")
	monkeypatch.setattr(stub_frappe, "get_single", lambda *a, **k: state)

	restore.after_restore({"restored_on": "2026-06-01 11:40:00"})

	assert ("files_reconciled_for", "2026-06-01 11:40:00") in state.writes
	assert len(stub_frappe.enqueued) == 1
	assert stub_frappe.enqueued[0][0] == "oneapp.onespace.restore.reconcile"


def test_the_next_sync_does_not_reconcile_again(restore, stub_frappe, monkeypatch):
	state = FakeState(reconciled_for="2026-06-01 11:40:00")
	monkeypatch.setattr(stub_frappe, "get_single", lambda *a, **k: state)

	restore.after_restore({"restored_on": "2026-06-01 11:40:00"})

	assert state.writes == [] and stub_frappe.enqueued == []


def test_a_workspace_that_was_never_restored_does_nothing(restore, stub_frappe):
	restore.after_restore({"requested": True})
	assert stub_frappe.enqueued == []


# --------------------------------------------------------------------------- #
# The stamp
# --------------------------------------------------------------------------- #

def test_a_stamp_reads_back_as_the_moment_it_names(restore):
	assert restore._stamp_to_datetime("20260412-031500") == datetime.datetime(
		2026, 4, 12, 3, 15, 0
	)


def test_something_that_is_not_a_stamp_is_not_a_moment(restore):
	assert restore._stamp_to_datetime("") is None
	assert restore._stamp_to_datetime("latest") is None


# --------------------------------------------------------------------------- #
# What a backup carries
# --------------------------------------------------------------------------- #

def test_a_workspace_with_a_bucket_does_not_tar_its_files(backup, stub_frappe, monkeypatch):
	"""They are already objects in the bucket the backup is written into.

	The tarball was a second copy of every attachment beside the first, charged
	for monthly, and a multi-gigabyte upload every night to produce it.
	"""
	taken = {}
	monkeypatch.setattr(
		backup, "now_datetime", lambda: datetime.datetime(2026, 6, 1, 12, 0, 0)
	)
	monkeypatch.setattr(backup, "files_live_in_the_bucket", lambda: True)
	monkeypatch.setattr(
		backup, "take", lambda with_files=True: taken.setdefault("files", with_files) or {}
	)
	monkeypatch.setattr(backup, "upload", lambda artifacts, prefix: [])
	reported = []
	monkeypatch.setattr(backup, "_report", lambda result: reported.append(result))

	from oneapp.onestorage import r2 as storage

	monkeypatch.setattr(storage, "is_configured", lambda: True)

	result = backup.run_backup(with_files=True)

	assert taken["files"] is False
	assert result["with_files"] is False and result["files_in_bucket"] is True
	# Said out loud, because the control plane refuses to promote a backup whose
	# files it cannot account for — and "no tarball" has to be distinguishable
	# from "the tarball failed".
	assert reported[0]["files_in_bucket"] is True
