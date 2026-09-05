"""Large files that go to R2 without passing through Python.

Four things worth a test, and they are the four that would each be a real
incident: an upload finished by somebody who did not start it, a workspace
billed for an object whose row was refused, a completion sent to R2 with its
parts out of order, and a file name carrying a path out of its tenant's prefix.

The bytes themselves are not here. What moves them is the browser and R2, and
the only thing this side of it decides is what may be signed and what the row
ends up saying.
"""

import json

import pytest


@pytest.fixture
def direct(stub_frappe):
	from oneapp.oneapp_core.storage import direct as module

	return module


MB = 1024 * 1024
BIG = 64 * MB


class FakeS3:
	"""The four calls a multipart upload makes, and what they remember."""

	def __init__(self):
		self.aborted = []
		self.completed = []
		self.deleted = []
		self.size = BIG

	def create_multipart_upload(self, Bucket, Key, ContentType=None):
		return {"UploadId": "upload-1"}

	def generate_presigned_url(self, operation, Params, ExpiresIn):
		return f"https://r2.example/{Params['Key']}?part={Params['PartNumber']}"

	def complete_multipart_upload(self, Bucket, Key, UploadId, MultipartUpload):
		self.completed.append(MultipartUpload["Parts"])

	def abort_multipart_upload(self, Bucket, Key, UploadId):
		self.aborted.append((Key, UploadId))

	def head_object(self, Bucket, Key):
		return {"ContentLength": self.size}

	def delete_object(self, Bucket, Key):
		self.deleted.append(Key)


class FakeDoc:
	"""What `frappe.get_doc({...})` hands back for a File being inserted."""

	def __init__(self, fields, inserted):
		self.fields = fields
		self.inserted = inserted
		self.name = "abc123"
		self.is_private = fields.get("is_private")
		self.file_name = fields.get("file_name")
		self.file_size = fields.get("file_size")
		self.file_url = ""

	def insert(self):
		self.inserted.append(self.fields)
		return self

	def db_set(self, field, value, update_modified=True):
		setattr(self, field, value)


def _configured(monkeypatch, direct, s3, tenant="acme", public_base=""):
	monkeypatch.setattr(direct.r2, "is_configured", lambda: True)
	monkeypatch.setattr(direct.r2, "client", lambda: s3)
	monkeypatch.setattr(
		direct.r2,
		"config",
		lambda: {
			"account_id": "a",
			"bucket": "space",
			"access_key": "k",
			"secret_key": "s",
			"public_base": public_base,
			"tenant": tenant,
		},
	)
	monkeypatch.setattr(direct.r2, "delete", lambda key: s3.delete_object("space", key))
	monkeypatch.setattr(direct.site, "is_control", lambda: False)
	monkeypatch.setattr(direct.quota, "check_room", lambda size: None)


class FakePermitted:
	"""A document the reader may write. `_may_write` asks nothing else of it."""

	def check_permission(self, level):
		return True


def _rows(monkeypatch, stub_frappe):
	"""Collect the File dicts that would have been inserted.

	`get_doc` is two functions in Frappe — one that fetches a document by name
	and one that builds a new one from a dict — and this module calls both.
	"""
	inserted = []

	def get_doc(first, *rest):
		if rest:
			return FakePermitted()
		return FakeDoc(first, inserted)

	monkeypatch.setattr(stub_frappe, "get_doc", get_doc)
	return inserted


def _begun(direct, size=BIG, **kwargs):
	return direct.begin(file_name="clip.mp4", file_size=size, **kwargs)


# --------------------------------------------------------------------------- #
# When the direct path applies at all
# --------------------------------------------------------------------------- #

def test_a_small_file_is_told_to_post_it_the_ordinary_way(direct, monkeypatch):
	_configured(monkeypatch, direct, FakeS3())
	assert _begun(direct, size=direct.THRESHOLD - 1) == {"direct": False}


def test_a_site_with_no_bucket_is_told_the_same(direct, monkeypatch):
	s3 = FakeS3()
	_configured(monkeypatch, direct, s3)
	monkeypatch.setattr(direct.r2, "is_configured", lambda: False)
	assert _begun(direct) == {"direct": False}


def test_the_control_plane_never_takes_this_path(direct, monkeypatch):
	_configured(monkeypatch, direct, FakeS3())
	monkeypatch.setattr(direct.site, "is_control", lambda: True)
	assert _begun(direct) == {"direct": False}


def test_the_quota_is_checked_before_anything_is_signed(direct, monkeypatch):
	"""The whole reason this is a handshake and not one call.

	A full workspace has to be a refusal in the browser rather than two
	gigabytes uploaded and then thrown away.
	"""
	s3 = FakeS3()
	_configured(monkeypatch, direct, s3)

	def full(size):
		raise direct.quota.StorageQuotaExceeded("Storage limit reached.")

	monkeypatch.setattr(direct.quota, "check_room", full)

	with pytest.raises(direct.quota.StorageQuotaExceeded):
		_begun(direct)

	assert s3.aborted == []


# --------------------------------------------------------------------------- #
# The handshake
# --------------------------------------------------------------------------- #

def test_begin_keys_the_object_under_its_tenant(direct, monkeypatch):
	_configured(monkeypatch, direct, FakeS3(), tenant="acme")
	started = _begun(direct)

	assert started["direct"] is True
	assert started["key"].startswith("tenants/acme/private/uploads/")
	assert started["key"].endswith("/clip.mp4")


def test_begin_signs_the_first_batch_and_no_more(direct, monkeypatch):
	_configured(monkeypatch, direct, FakeS3())
	# Large enough to need more parts than one batch of signatures.
	started = _begun(direct, size=direct.MIN_PART * 120)

	assert started["parts"] == 120
	assert len(started["urls"]) == direct.BATCH
	assert [one["part"] for one in started["urls"]] == list(range(1, direct.BATCH + 1))


def test_more_urls_can_be_minted_as_the_upload_walks(direct, monkeypatch):
	_configured(monkeypatch, direct, FakeS3())
	started = _begun(direct, size=direct.MIN_PART * 120)

	more = direct.sign(
		key=started["key"],
		upload_id=started["upload_id"],
		token=started["token"],
		first=51,
		count=10,
	)
	assert [one["part"] for one in more["urls"]] == list(range(51, 61))


def test_part_size_keeps_the_count_under_the_ceiling(direct):
	huge = 400 * 1024 ** 3
	size = direct._part_size(huge)
	assert size % (1024 * 1024) == 0
	assert huge / size <= direct.MAX_PARTS


# --------------------------------------------------------------------------- #
# Who may finish an upload
# --------------------------------------------------------------------------- #

def test_a_forged_token_cannot_finish_an_upload(direct, monkeypatch):
	_configured(monkeypatch, direct, FakeS3())
	started = _begun(direct)

	with pytest.raises(Exception) as raised:
		direct.finish(
			key=started["key"],
			upload_id=started["upload_id"],
			token="not the token",
			parts=json.dumps([{"part": 1, "etag": "e1"}]),
			file_name="clip.mp4",
		)
	assert "not yours" in str(raised.value)


def test_the_token_is_bound_to_the_person_who_started_it(direct, monkeypatch, stub_frappe):
	_configured(monkeypatch, direct, FakeS3())
	started = _begun(direct)

	stub_frappe.session.user = "someone.else@example.com"
	with pytest.raises(Exception):
		direct.abort(started["key"], started["upload_id"], started["token"])


# --------------------------------------------------------------------------- #
# Finishing
# --------------------------------------------------------------------------- #

def test_finish_makes_a_row_that_already_points_at_the_object(direct, monkeypatch, stub_frappe):
	s3 = FakeS3()
	_configured(monkeypatch, direct, s3)
	rows = _rows(monkeypatch, stub_frappe)
	started = _begun(direct)

	answer = direct.finish(
		key=started["key"],
		upload_id=started["upload_id"],
		token=started["token"],
		parts=json.dumps([{"part": 1, "etag": "e1"}]),
		file_name="clip.mp4",
		folder="Home",
	)

	assert len(rows) == 1
	# `r2_key` at insert time and not after: `OneSpaceFile.after_insert` reads
	# it to decide whether to move the bytes, and they are already there.
	assert rows[0]["r2_key"] == started["key"]
	assert rows[0]["folder"] == "Home"
	assert answer["name"] == "abc123"
	assert answer["file_url"].endswith("download?file=abc123")


def test_the_row_is_inserted_with_a_remote_url_and_not_an_empty_one(
	direct, monkeypatch, stub_frappe
):
	"""Found by inserting one for real, and invisible from here otherwise.

	`File.validate_file_on_disk` does not ask whether a file is remote — it asks
	whether the path starts with a URL prefix. An empty `file_url` does not, so
	the insert fails with `File  does not exist`, the name of the missing file
	blank because there is no name. The placeholder goes in first and the real
	URL replaces it once the row has been named.
	"""
	s3 = FakeS3()
	_configured(monkeypatch, direct, s3)
	rows = _rows(monkeypatch, stub_frappe)
	started = _begun(direct)

	direct.finish(
		key=started["key"],
		upload_id=started["upload_id"],
		token=started["token"],
		parts=json.dumps([{"part": 1, "etag": "e1"}]),
		file_name="clip.mp4",
	)

	inserted = rows[0]["file_url"]
	assert inserted.startswith("/api/method/")
	# Unique per upload: `validate_private_file_access` refuses a URL another
	# row already carries, so one abandoned upload would otherwise refuse the
	# next person's.
	assert started["key"] in inserted


def test_the_size_is_what_r2_holds_and_not_what_the_browser_claimed(
	direct, monkeypatch, stub_frappe
):
	s3 = FakeS3()
	s3.size = 12345
	_configured(monkeypatch, direct, s3)
	rows = _rows(monkeypatch, stub_frappe)
	started = _begun(direct, size=BIG)

	direct.finish(
		key=started["key"],
		upload_id=started["upload_id"],
		token=started["token"],
		parts=json.dumps([{"part": 1, "etag": "e1"}]),
		file_name="clip.mp4",
	)

	assert rows[0]["file_size"] == 12345


def test_parts_are_sorted_before_they_go_back_to_r2(direct, monkeypatch, stub_frappe):
	"""Parts upload in parallel and come back in whatever order they finished.

	S3 rejects a completion whose part numbers are not ascending, and the
	failure would be at the very end of a very long upload.
	"""
	s3 = FakeS3()
	_configured(monkeypatch, direct, s3)
	_rows(monkeypatch, stub_frappe)
	started = _begun(direct)

	direct.finish(
		key=started["key"],
		upload_id=started["upload_id"],
		token=started["token"],
		parts=json.dumps([
			{"part": 3, "etag": "e3"},
			{"part": 1, "etag": "e1"},
			{"part": 2, "etag": "e2"},
		]),
		file_name="clip.mp4",
	)

	assert [one["PartNumber"] for one in s3.completed[0]] == [1, 2, 3]


def test_a_refused_row_takes_the_object_with_it(direct, monkeypatch, stub_frappe):
	"""The quota hook throws at `before_insert`, which is after the bytes have
	landed. An upload the workspace was refused must not be one it is billed
	for."""
	s3 = FakeS3()
	_configured(monkeypatch, direct, s3)

	def refuse(first, *rest):
		if rest:
			return FakePermitted()
		raise direct.quota.StorageQuotaExceeded("Storage limit reached.")

	monkeypatch.setattr(stub_frappe, "get_doc", refuse)
	started = _begun(direct)

	with pytest.raises(direct.quota.StorageQuotaExceeded):
		direct.finish(
			key=started["key"],
			upload_id=started["upload_id"],
			token=started["token"],
			parts=json.dumps([{"part": 1, "etag": "e1"}]),
			file_name="clip.mp4",
		)

	assert s3.deleted == [started["key"]]


def test_an_upload_that_sent_nothing_is_refused(direct, monkeypatch):
	_configured(monkeypatch, direct, FakeS3())
	started = _begun(direct)

	with pytest.raises(Exception) as raised:
		direct.finish(
			key=started["key"],
			upload_id=started["upload_id"],
			token=started["token"],
			parts="[]",
			file_name="clip.mp4",
		)
	assert "no parts" in str(raised.value)


# --------------------------------------------------------------------------- #
# The name
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
	"given,expected",
	[
		("clip.mp4", "clip.mp4"),
		("../../etc/passwd", "passwd"),
		("C:\\Users\\me\\plan.pdf", "plan.pdf"),
		("  spaced.txt  ", "spaced.txt"),
	],
)
def test_a_file_name_never_carries_a_path(direct, given, expected):
	assert direct._safe_name(given) == expected


@pytest.mark.parametrize("given", ["", "   ", "..", "some/dir/"])
def test_a_name_that_is_only_a_path_is_refused(direct, given):
	with pytest.raises(Exception):
		direct._safe_name(given)


def test_a_public_file_is_served_from_the_cdn(direct, monkeypatch, stub_frappe):
	s3 = FakeS3()
	_configured(monkeypatch, direct, s3, public_base="https://cdn.4dl.app")
	rows = _rows(monkeypatch, stub_frappe)
	started = _begun(direct, is_private=0)

	answer = direct.finish(
		key=started["key"],
		upload_id=started["upload_id"],
		token=started["token"],
		parts=json.dumps([{"part": 1, "etag": "e1"}]),
		file_name="clip.mp4",
	)

	# `finish` is not told whether the file is private — it reads it off the
	# key, which the token vouches for.
	assert rows[0]["is_private"] == 0
	assert answer["file_url"] == f"https://cdn.4dl.app/{started['key']}"


# --------------------------------------------------------------------------- #
# CORS
# --------------------------------------------------------------------------- #

def test_the_cors_policy_exposes_the_etag(direct):
	"""Without this, every byte uploads correctly and the completion fails: the
	browser cannot read a response header the bucket does not expose, and the
	ETags are what completes a multipart upload."""
	rules = direct.r2.cors_rules(["https://acme.4dl.app"])
	assert rules[0]["ExposeHeaders"] == ["ETag"]
	assert "PUT" in rules[0]["AllowedMethods"]
	assert rules[0]["AllowedOrigins"] == ["https://acme.4dl.app"]
