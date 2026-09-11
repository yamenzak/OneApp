app_name = "oneapp"
app_title = "OneSpace"
app_publisher = "Four Degree Labs"
app_description = "Unified application surface for Four Degree Labs tenants."
app_email = "hello@fourdegreelabs.com"
app_license = "agpl-3.0"

# Deliberately not `required_apps = ["erpnext"]`.
#
# Nothing in this app imports erpnext at module level: every import in
# onespace/books.py is deferred inside a function and gated on
# `erpnext_installed()`, and `books.status()` answers `available: False` when it
# is absent — which the workspace's Books panel renders as "No accounting app".
#
# So the hard requirement claimed a dependency the code does not have, and the
# only thing it actually stopped was running OneSpace anywhere erpnext is not
# installed — including every development bench, which is why this SPA went so
# long without being opened in a browser. Tenant benches still carry erpnext.

# ---------------------------------------------------------------------------
# SPA
# ---------------------------------------------------------------------------
# The Vue router owns everything under /one. Without this rule Frappe resolves
# only the exact route, so reloading any deep link serves a 404 before the router
# ever runs. The desk at /app is left alone rather than used — see docs/ONEADMIN.md, No desk.
website_route_rules = [
	{"from_route": "/one/<path:app_path>", "to_route": "one"},
]

# Signing in lands on the workspace, not the desk. Frappe's fallback is "me",
# which it rewrites to "desk" for any System User.
home_page = "one"

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
# Attachments go to R2 rather than the server filesystem. The override falls
# back to Frappe's normal behaviour when R2 is not configured, so a site without
# keys still works instead of failing every upload.
override_doctype_class = {
	"File": "oneapp.onestorage.file.OneSpaceFile",
	# Mail arrives folder by folder and the framework throws the folder away —
	# `InboundMail` is handed it and nothing on the Communication records where
	# the message was filed, so somebody's Applicants folder lands in one flat
	# list. One method is overridden to carry it through, and one guard is
	# relaxed inside a Sent folder so sent mail is not skipped as "your own mail
	# in your own inbox". See `onemail/folders.py`.
	"Email Account": "oneapp.onemail.folders.OneSpaceEmailAccount",
}

# ---------------------------------------------------------------------------
# Document hooks
# ---------------------------------------------------------------------------
# A share link names a file, and Frappe refuses to delete anything another
# document links to. Without this, sharing a drawing once makes that drawing
# undeletable for ever — with an error naming a doctype the person has never
# heard of. The links go with the file instead; `storage.file` deletes them.
ignore_links_on_delete = ["File Link"]

doc_events = {
	"File": {
		# Storage quota is enforced at upload time. Discovering you are 3 GB over
		# after the fact is a worse experience than a clear rejection now.
		#
		# And what the file is, so the Drive can filter on a column rather than
		# walking a mime map per row per page — see `onestorage`.
		"before_insert": [
			"oneapp.onestorage.quota.enforce_quota",
			"oneapp.onestorage.on_insert",
		],
		# A sheet's grid is a `Sheet Book` row, and the File being deleted is
		# the only thing that knows they exist. Without this the bin's
		# thirty-day sweep leaves behind the workbook of every sheet anybody
		# ever threw away — see `onesheet`.
		# A sheet's grid, a document's prose and either one's earlier drafts are
		# rows keyed by the File, and the File being deleted is the only thing
		# that knows they exist. See `onesheet`, `onedoc`
		# and `shared/versions.py`.
		"on_trash": [
			"oneapp.onesheet.on_trash",
			"oneapp.onedoc.on_trash",
			"oneapp.shared.versions.on_trash",
			# And which records it read. `Bound Record` rows are keyed by the
			# File the same way, and a row pointing at a file that is gone is
			# a row nothing will ever ask about again.
			"oneapp.shared.binding.on_file_trash",
		],
	},
	"Email Queue": {
		# Frappe queues one document per send, so counting them measures what
		# actually leaves the site.
		"before_insert": "oneapp.onemail.outbound.enforce_send_rate",
		# A permanent failure names an address that will fail again. Read it
		# here rather than waiting for a provider webhook: an address that does
		# not exist is refused at SMTP time and the reason is already on the row.
		"on_update": "oneapp.onemail.suppression.on_queue_failure",
	},
	# Following a document. Frappe stores the follow and then only ever emails a
	# digest about it, so these two are the in-app half — see
	# `onespace.notifications`, "Following a document".
	#
	# Version and Comment rather than `on_update` for `*`: they are the same two
	# sources the framework's own digest reads, and a Version row exists only
	# where `track_changes` is on, which is exactly the condition a document has
	# to meet to be followable at all.
	# Retention: the part of an invoice a construction customer keeps until the
	# job is proved. Inert unless the invoice carries the field — see
	# `onespace/retention.py`, which is also the argument for why a
	# subcontractor's books are wrong without it.
	"Sales Invoice": {
		"validate": "oneapp.onespace.retention.apply",
	},
	# Which source's answer the network is drawn from. Precedence is a setting
	# a customer changes expecting the map to change, not a number that takes
	# effect on the next delivery — see `onemobility/conflicts.py`.
	"Transit Source": {
		"on_update": "oneapp.onemobility.conflicts.on_source_change",
	},
	"Version": {
		"after_insert": "oneapp.onespace.notifications.on_version",
	},
	"Comment": {
		"after_insert": "oneapp.onespace.notifications.on_comment",
	},
	# A face on a contact and a logo on a company, looked up once and stored
	# here. Both events, because a contact is very often created with no
	# address and given one a minute later — and that second save is the first
	# moment there is anything to look up. Off unless an operator turned it
	# on; see `onemail/faces.py`, which is also where the argument with
	# `people.py` about third-party avatars is settled.
	"Contact": {
		"after_insert": "oneapp.onemail.faces.on_save",
		"on_update": "oneapp.onemail.faces.on_save",
	},
	"Company": {
		"after_insert": "oneapp.onemail.faces.on_save",
		"on_update": "oneapp.onemail.faces.on_save",
	},
	"Communication": {
		# Which conversation this message belongs to, taken from the one it
		# answers rather than from its subject line — see
		# `onemail/threading.py`. `before_insert`, because the value
		# belongs to the row being written and setting it afterwards would be a
		# second version row on a doctype people already find noisy.
		# Two, and the order is the point: linking reads the thread key that
		# threading writes. Frappe runs a list of handlers in order, so this is
		# a sequence and not two independent hooks that happen to both fire.
		"before_insert": [
			"oneapp.onemail.threading.on_insert",
			# Which records this message is about — see
			# `onemail/linking.py`. Same `before_insert` argument as
			# above, and one more: `timeline_links` is a child table, and a
			# child row appended after the parent is saved is a second write.
			"oneapp.onemail.linking.on_insert",
		],
		# And how each link was made, after the framework has stopped rewriting
		# the rows it was written on — `deduplicate_timeline_links` rebuilds
		# every one of them from its doctype and name alone. See
		# `linking.stamp`, which is the whole reason this is two hooks.
		"after_insert": [
			"oneapp.onemail.linking.stamp",
			# A shared mailbox has a shared inbox, and shared sent mail.
			# Frappe's IMAP sync and our own composer both write a
			# `Communication` only its owner could read, so an address granted
			# to three people was one three could send from and one could read.
			# See `email/inbound.share_with_holders`.
			"oneapp.onemail.inbound.share_with_holders",
		],
		# Whose signature goes on a message is a question the framework answers
		# wrongly here — the site's default outgoing account signs everything,
		# whichever address it was actually sent from. Ours goes on in the
		# composer, where somebody can see it. See `email/signatures.py`.
		"before_save": "oneapp.onemail.signatures.hold_the_frameworks_signature",
	},
	# Inserts are what grow a database, so they are what pauses when a workspace
	# is over its allowance. Updates and deletes keep working, so deleting
	# something is always a way back. The check reads a cached verdict — the
	# measurement is an information_schema scan and must not run per insert.
	"*": {
		"before_insert": "oneapp.onestorage.quota.enforce_database_quota",
		# A field a person rewrote is not the model's any more, and the marks
		# go when the document goes. `*` because the mark is about a value on
		# any doctype — a workspace's records belong to apps we do not own, so
		# there is no list to name instead. The cost is a comparison against
		# the document the framework is already holding for its own Version
		# row, and on a document with no marks one indexed read; the doctypes
		# that save constantly and can never carry a mark are skipped before
		# the query. See `onespace/ai/written.py`.
		"on_update": [
			"oneapp.onespace.ai.written.forget_changed",
			# And what the record now says, as a direction, so mail can be
			# matched to it. Enqueued and deduplicated per record, and skipped
			# before any query for the doctypes no space exposes — see
			# `onespace/ai/index.py`.
			"oneapp.onespace.ai.index.on_save",
		],
		"after_insert": "oneapp.onespace.ai.index.on_save",
		"on_trash": [
			"oneapp.onespace.ai.written.forget_deleted",
			"oneapp.onespace.ai.index.on_delete",
		],
	},
}

# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# AI features
# ---------------------------------------------------------------------------
# Modules holding @ai_feature declarations. Listed rather than discovered by
# walking the package: a feature that only registers when something happens to
# import its module is a feature missing from the settings page on a cold worker.
#
# Apps built on OneSpace add their own here. The workspace assistant is the first
# one shipped, and it is the mechanism working rather than an exception to it:
# it gets its settings row, its model picker, its credit hold and its entry in
# the operator registry from the decorator, like anything else would.
ai_features = [
	"oneapp.onespace.chat.assistant",
	# The verbs, declared once for the whole product — see `docs/AI.md` §2.2.
	# A module that wants "improve this" imports these rather than declaring
	# its own, so there is one prompt to tune and one settings row to switch.
	"oneapp.onespace.ai.text",
	# And the one a module owns because nothing else could: answering a thread.
	"oneapp.onemail.intelligence",
	# Which record a conversation is about, once retrieval has produced a
	# shortlist to choose from — see `onemail/filing.py`.
	"oneapp.onemail.filing",
	# And the document's own two: a passage at the cursor, and a whole
	# document written from its headings — see `onedoc/intelligence.py`.
	"oneapp.onedoc.intelligence",
	# And the retrieval itself, which is a feature because an embedding is a
	# metered call like any other: a model picker, a switch, a credit hold.
	"oneapp.onespace.ai.index",
]

# Modules that register what a model may *ask for* — see `onespace/ai/actions.py`.
# The same shape as `ai_features` and for the same reason: a kind that only
# registers when something happens to import its module is a card that fails to
# apply on a cold worker.
#
# The three the spine ships with belong to no module in particular: a record, a
# date in somebody's diary, a task. An app adds its own here.
ai_actions = [
	"oneapp.onespace.ai.kinds",
	# Mail's own: file this message against that record.
	"oneapp.onemail.filing",
]

scheduler_events = {
	"cron": {
		# Entitlements and balance. Frequent because revoking an app should take
		# effect in minutes, not hours.
		"*/15 * * * *": ["oneapp.onespace.sync.sync_from_control_plane"],
		# And the live streams, which are the one scheduled thing here that is
		# not a sweep: each run opens a window on every socket source and holds
		# it for just under five minutes, so the runs form a chain rather than
		# a series of polls. A stream that had no end would be a job nobody
		# could restart — see `onemobility/streaming.py`.
		"*/5 * * * *": ["oneapp.onemobility.streaming.run_streams"],
	},
	"daily": [
		# The register of things that expire — licences, visas, insurance — and
		# the warning before one does. Daily because a status derived on save
		# goes stale the moment the date changes: a licence that was Valid last
		# night is Expiring this morning and nobody saved it.
		"oneapp.onespace.expiry.sweep",
		# And the other thing with an end date on it: an out-of-office reply
		# whose last day has passed. Without something acting on the date, the
		# date is a note to self.
		"oneapp.onemail.rules.expire_away",
		# And the bin, which is a promise with a date on it: thirty days, then
		# the row and the R2 object go together. Without this the promise is
		# that we keep everything anybody ever deleted, and bill for it.
		"oneapp.onestorage.sweep_trash",
		# And the share links that expired a month ago. Not the moment they
		# expire: the row is the audit trail, and "this stopped working last
		# Tuesday" is a question asked in the week after it stops.
		"oneapp.onestorage.sweep_links",
		# And the automatic versions of a sheet or a document that are now too
		# dense to be worth their bytes. Named versions are not in its reach —
		# see `shared/versions.py`.
		"oneapp.shared.versions.thin",
		# And the fact tables: tomorrow's partition opened, yesterday rolled up
		# into the tier that stays, and anything past its hot window frozen
		# into R2 and dropped. Nightly and not hourly because the unit of every
		# one of those is a day. A workspace with no declared fact table does
		# nothing here. See `shared/facts.py`.
		# Yesterday's positions turned into stop visits, *before* the sweep
		# below can drop the partition they were derived from. Order is the
		# whole of it: a visit inferred from rows that are already in R2 is a
		# visit nobody infers. See `onemobility/arrivals.py`.
		"oneapp.onemobility.arrivals.build",
		"oneapp.shared.facts.sweep",
		# And last, because it depends on both: yesterday's claims settled
		# against the roll-up the sweep has just written, then tomorrow's made
		# off a history that now includes yesterday. A forecast nobody scores is
		# a decoration — see `onemobility/scoring.py`.
		"oneapp.onemobility.scoring.nightly",
	],
	"hourly": [
		"oneapp.onespace.sync.report_usage_to_control_plane",
		# Backups, into R2, on the frequency the plan bought. Hourly rather than
		# daily because the frequency is a plan term and cannot be a cron line:
		# this wakes every hour and decides whether this hour is one of the
		# slots. See `onespace/backup.py`.
		"oneapp.onespace.backup.scheduled_backup",
		# Re-measures the database and caches the verdict the insert hook reads,
		# so a workspace that frees space is unblocked without waiting out the
		# cache, and one that fills up is caught within the hour.
		"oneapp.onestorage.quota.refresh_database_verdict",
		# And the transit sources that are asked rather than pushed. Hourly for
		# the same reason backups are: how often a source is fetched is a
		# setting on the source, and a setting cannot be a cron line — so this
		# wakes every hour and works out which sources this hour is a slot for.
		# A workspace with no OneMobility reads an empty table.
		"oneapp.onemobility.sources.poll",
	],
	"weekly_long": [
		# Objects in the bucket that no `File` row claims any more. After a
		# restore this is thousands and runs within the quarter hour, from the
		# sync — this is the other case, the ones and twos left by an upload
		# that put the object and then failed to write the row. Weekly because
		# that is a slow leak rather than a fault, and long because listing a
		# bucket prefix is a walk. See `onespace/restore.py`.
		"oneapp.onespace.restore.sweep",
	],
}

# Fetch a transit source on demand, from the screen it is listed on. Declared
# in code behind the hook rather than stored on the Space: an action names a
# method somebody can invoke, and that list is not a row an operator edits.
onespace_screen_actions = ["oneapp.onemobility.actions.actions"]

# A space with a setting of its own, through the same door an installed app
# uses. OneMobility's two are how long a workspace keeps its vehicle detail and
# its frozen copy of it — see `onemobility/settings.py`. The group carries a
# `when`, so a workspace without the space is not offered it.
onespace_settings_groups = ["oneapp.onemobility.settings.groups"]

after_install = "oneapp.install.after_install"

# Our own Notification Type, seeded the way the framework seeds its five: in
# code, idempotently, on install and on every migrate. A type is a doctype row,
# so an app adds one rather than forking an enum.
after_migrate = [
	"oneapp.onespace.notifications.install_types",
	# The custom fields, for a site installed before one of them existed. Both
	# are idempotent and both are cheap; the alternative is a patch per field.
	"oneapp.install.create_custom_fields",
]

# `Workspace` never sends its own email.
#
# Every notice under it — a declined card, a workspace archived, a quota
# reached — is already an email the *control plane* sent the moment it
# happened, from the side that knows the billing address and owns the wording.
# The in-app notification is the second half of that, not a duplicate of it, and
# `is_email_notifications_enabled_for_type` reads this hook to keep it so.
# `Following` never sends its own email either, and for a different reason:
# following a busy record is one email per save. Frappe's answer to that is the
# Hourly/Daily/Weekly digest in `send_document_follow_mails`, which is the right
# shape for email and needs a frequency preference we have not built — so a
# follow is an in-app subscription and says so, rather than quietly filling an
# inbox. The digest is left alone: `User.document_follow_notify` stays 0.
# And an `Alert` is emailed by the rule that sent it. A rule set to "By email"
# calls `send_an_email`, which builds a Communication and sends — it never asks
# `Notification Settings`, because an alert an admin wrote about an overdue
# invoice is not a thing the recipient opted into. That is Frappe's call and the
# right one; what would be wrong is a switch in the panel that looks like it
# turns those emails off. So the app half is a real choice and the email half
# says who owns it.
notification_skip_email_types = ["Workspace", "Following", "Alert"]
