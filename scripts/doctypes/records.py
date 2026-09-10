"""Tenant-side records that are not part of any framework.

A compliance document, a piece of correspondence, a mail rule: the things a
workspace keeps because the business keeps them, not because the platform needs
them.
"""

from .spec import READONLY_PERMS, column, doctype, f, section


# --------------------------------------------------------------------------- #
# The two registers every business keeps and no ERP models
#
# Both came out of reading a real customer's system — an Abu Dhabi contractor —
# and both are here rather than in that customer's space because neither is
# theirs. A licence that expires and a letter that has to be numbered are what
# a company *is*, not what a company *does*, and the version of each written per
# customer is written badly and separately every time.
#
# ERPNext models neither. HRMS has an employee-document idea, which is narrower
# than the question by an order of magnitude: a trade licence, a vehicle
# registration and a site insurance policy all expire, none of them belongs to
# an employee, and the fine is the same.
# --------------------------------------------------------------------------- #
doctype(
    "Compliance Document",
    app="tenant",
    autoname="format:CD-{YY}-{#####}",
    search_fields="title,document_number,about",
    title_field="title",
    states=[
        ("Expired", "Red"),
        ("Expiring", "Orange"),
        ("No expiry", "Gray"),
        ("Valid", "Green"),
    ],
    fields=[
        f("title", reqd=1, in_list_view=1,
          description="What the paper is called: Trade Licence, Residence Visa."),
        f("category", "Select", in_list_view=1,
          options="\n".join(["", "Licence", "Visa", "Permit", "Registration",
                             "Insurance", "Certificate", "Contract", "Identity",
                             "Other"])),
        f("document_number", in_list_view=1),
        column("cb_doc_dates"),
        f("issue_date", "Date"),
        # The whole reason this doctype exists. Everything else on it is
        # bookkeeping around this one date.
        f("expiry_date", "Date", in_list_view=1,
          description="Empty is a document that does not expire — an academic "
                      "certificate, a deed. It is not the same as unknown, and "
                      "the status says so."),
        f("status", "Select",
          # Listed in urgency order, which is also alphabetical order, which
          # is what the compliance screen's `status asc` relies on. Not a
          # coincidence and not safe to rename casually: SQL sorts a null
          # expiry date above every real one, so a register ordered by date
          # leads with the documents that never expire. See
          # `test_the_statuses_sort_into_urgency`.
          options="\n".join(["Expired", "Expiring", "No expiry", "Valid"]),
          default="No expiry", read_only=1, in_list_view=1,
          description="Worked out from the expiry date and the warning window, "
                      "on save and once a day. Never typed: a status somebody "
                      "can set is a status that disagrees with the date beside "
                      "it."),
        section("sec_cd_about", "What it belongs to"),
        # Anything. A visa belongs to an employee, a trade licence to the
        # company, a vehicle registration to an asset, an insurance policy to a
        # project — and a register that only knew about one of those would be
        # four registers within a year.
        f("about_doctype", "Link", options="DocType", label="Belongs to",
          description="Anything on this site: an employee, a company, a "
                      "vehicle, a project."),
        f("about", "Dynamic Link", options="about_doctype", label="Which one",
          in_list_view=1),
        column("cb_cd_issue"),
        f("issued_by", description="The authority that issued it."),
        f("place_of_issue"),
        section("sec_cd_warning", "Warning"),
        # A Heading and an HTML block: the doctype's author annotating their own
        # form. Both are layout fields, so neither carries a value and neither
        # is ever a column — and both were silently dropped by the record form
        # until it learned to draw them. Here as much as anywhere else because
        # this is the fixture that proves it: `e2e/form-notes.spec.js`.
        f("h_cd_warning", "Heading", "Before it lapses"),
        f("note_cd_warning", "HTML", "",
          options="<p>The warning goes to whoever is <b>following</b> this "
                  "document, once — not every morning until somebody acts, "
                  "which is how people learn to ignore it.</p>"),
        f("remind_days", "Int", default="30", label="Warn this many days ahead",
          description="How long before the expiry this starts saying so. Thirty "
                      "days is a month to renew a licence; a visa wants more."),
        f("reminded_on", "Date", read_only=1,
          description="When the last warning went out. Kept so a daily job "
                      "warns once and not every morning until somebody acts, "
                      "which is how people learn to ignore it."),
        column("cb_cd_renewal"),
        # A renewal is a new document that replaces an old one, and saying so
        # turns a register into a history: what this licence was before, and
        # before that.
        f("renews", "Link", options="Compliance Document",
          description="The document this one replaces. The old one is kept: "
                      "an expired licence is still what you were trading under "
                      "last year."),
        f("renewed_by", "Link", options="Compliance Document", read_only=1,
          description="Filled in on the old document when a new one names it."),
        section("sec_cd_file", "The document itself"),
        f("file", "Attach", label="Scan"),
        f("notes", "Small Text"),
    ],
)


doctype(
    "Correspondence",
    app="tenant",
    module="OneMail",
    autoname="naming_series:",
    search_fields="subject,to_party",
    title_field="subject",
    states=[("Draft", "Gray"), ("Issued", "Green"), ("Cancelled", "Red")],
    fields=[
        f("naming_series", "Select", options="LTR-.YY.-\nFRM-.YY.-\nMEM-.YY.-",
          default="LTR-.YY.-", reqd=1,
          description="A letter and a form are numbered in separate sequences, "
                      "because that is what somebody quoting one on the phone "
                      "expects."),
        f("kind", "Select", options="Letter\nForm\nMemo\nNotice",
          default="Letter", in_list_view=1),
        f("letter_date", "Date", label="Date", in_list_view=1),
        column("cb_corr_state"),
        f("status", "Select", options="Draft\nIssued\nCancelled",
          default="Draft", in_list_view=1),
        f("is_template", "Check", default="0", label="This is a template",
          description="A letter kept to start others from. Templates are not "
                      "numbered against the real sequence."),
        f("cancellation_reason", "Small Text", depends_on="eval:doc.status=='Cancelled'"),
        section("sec_corr_en", "English"),
        # Both languages, side by side, and neither is the "real" one. A UAE
        # contractor writes to a municipality in Arabic and to a consultant in
        # English, often about the same thing on the same day.
        f("subject", in_list_view=1),
        f("to_party", label="To"),
        f("body", "Text Editor"),
        section("sec_corr_ar", "العربية"),
        f("subject_ar", label="الموضوع"),
        f("to_party_ar", label="إلى"),
        f("body_ar", "Text Editor", label="النص"),
        section("sec_corr_about", "What it is about"),
        f("about_doctype", "Link", options="DocType", label="About"),
        f("about", "Dynamic Link", options="about_doctype", label="Which one"),
        column("cb_corr_sign"),
        f("signed_by"),
        f("signed_by_title", label="Title"),
        f("signed_by_ar", label="التوقيع"),
        f("signed_by_title_ar", label="الصفة"),
        section("sec_corr_files", "Files"),
        f("signature", "Attach Image"),
        f("issued_file", "Attach", label="Signed copy",
          description="The one that was actually sent, scanned back in."),
    ],
)


# --------------------------------------------------------------------------- #
# Mail Rule — "put anything from the architect in Al Reem".
#
# Frappe has an `Email Rule` and it is not this: two fields, an address and a
# spam flag. What people mean by a rule is a filing instruction, and every mail
# client has had one for thirty years — without it a shared inbox is sorted by
# hand, every morning, forever.
#
# Deliberately small. One condition, not a boolean tree: the rules people
# actually write are "from this person" or "with this word in the subject", and
# a builder that can express `(A or B) and not C` is a builder nobody uses to
# express anything. Two rules are the answer to two conditions.
# --------------------------------------------------------------------------- #
doctype(
    "Mail Rule",
    app="tenant",
    module="OneMail",
    autoname="format:MR-{#####}",
    title_field="title",
    search_fields="title,address,matches",
    fields=[
        f("title", reqd=1, in_list_view=1,
          description="What this rule is for, in the words of whoever wrote it."),
        f("address", "Data", reqd=1, in_list_view=1, in_standard_filter=1,
          description="The mailbox it applies to. A rule belongs to an address, "
                      "not to a workspace: `sales@` and `ap@` sort differently."),
        f("enabled", "Check", default="1", in_list_view=1),
        # Order matters, and the first match wins — which is what makes a rule
        # list readable. Without it two rules that both match are a coin toss.
        f("priority", "Int", default="10", in_list_view=1,
          description="Lower runs first. The first rule that matches wins."),
        f("field", "Select", options="Sender\nSubject\nRecipient\nBody",
          default="Sender", reqd=1,
          description="What is looked at."),
        f("operator", "Select", options="Contains\nIs\nStarts with\nEnds with",
          default="Contains", reqd=1),
        f("matches", "Data", reqd=1, in_list_view=1,
          description="The text to look for. Case is ignored, because nobody "
                      "means it when they type an address."),
        f("into", "Data",
          description="The folder to file it in. Made on the mailbox if it is "
                      "not there yet."),
        f("mark_read", "Check", default="0",
          description="For the rules that file things nobody needs to look at."),
        f("star", "Check", default="0",
          description="And for the ones that file things somebody does."),
    ],
)


# --------------------------------------------------------------------------- #
# A link that outlives a session
#
# The one thing the framework genuinely does not have. `is_private` is a
# site-wide flag with no expiry and no audit; "send this drawing to the
# consultant until Friday" is the actual request, and it needs a row.
#
# Frappe Drive calls this a `Drive Token` and the idea is worth taking: a file,
# a secret, and a date. What is not taken is its permission model — see §3 of
# `docs/DRIVE.md`.
# --------------------------------------------------------------------------- #
doctype(
    "File Link",
    app="tenant",
    module="OneStorage",
    autoname="hash",
    title_field="label",
    search_fields="label,file",
    perms=READONLY_PERMS,
    fields=[
        f("file", "Link", options="File", reqd=1, in_list_view=1,
          description="The one file this link hands over. A folder is not "
                      "offered: a link to a folder is a link to everything "
                      "somebody puts in it afterwards."),
        f("label", "Data", in_list_view=1,
          description="What it was made for, in the words of whoever made it."),
        f("secret", "Data", reqd=1, unique=1, read_only=1,
          description="What is in the URL. Long enough not to be guessed, and "
                      "the only thing standing between the link and the file."),
        column("cb_link_when"),
        f("expires_on", "Datetime", in_list_view=1,
          description="After this the link is gone and the file is not. Empty "
                      "is refused on purpose: a link with no end is a file "
                      "published for ever by somebody who has left."),
        f("revoked", "Check", default="0", in_list_view=1,
          description="Taken back early. Kept rather than deleted, so 'who "
                      "shared this and when did it stop' has an answer."),
        f("opened", "Int", default="0", read_only=1,
          description="How many times it was followed."),
        f("last_opened", "Datetime", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Sheets
#
# A sheet is a `File` — see §5 Stage 1 of `docs/SHEETS.md`. That is why there is
# no `Sheet` doctype here: the File row is the sheet's identity, its name, its
# owner, its folder, its share, its place in the bin and its binding to a
# record. What this adds is the only thing a File cannot hold, which is a grid.
#
# One row per workbook and not one per cell, which is a reversal. The first
# build stored a `Sheet Cell` per cell so a read-back could be a query, and it
# was a defensible shape for a grid we had written ourselves. The grid is
# Frappe's now (`apps/oneapp/frontend/src/modules/onesheet/lib/VENDORED.md`): it holds the
# whole workbook in memory, saves it whole and loads it whole, and a second
# store the browser never reads would be a second thing to keep in step with no
# reader to justify it. Python reads the blob through
# `onesheet/codec.py`, which is where the argument is written out.
# --------------------------------------------------------------------------- #
doctype(
    "Sheet Book",
    app="tenant",
    module="OneSheet",
    autoname="field:sheet",
    title_field="sheet",
    search_fields="sheet",
    perms=READONLY_PERMS,
    fields=[
        f("sheet", "Data", reqd=1, unique=1, in_list_view=1,
          description="The File this workbook belongs to, by name. Data and "
                      "unique rather than a Link so the row is addressable as "
                      "`Sheet Book/<file>` — one statement to load, no filter."),
        f("payload", "Long Text",
          description="The workbook: every tab, cell, formula, format, merge, "
                      "named range, pivot and chart, as the gzipped envelope "
                      "`codec.py` reads. Never edited here — a save replaces "
                      "it whole, which is what the editor does."),
        column("cb_book_size"),
        f("byte_size", "Int", read_only=1,
          description="Uncompressed size of the payload. The number a size cap "
                      "has to be measured against, since the compressed one "
                      "says nothing about what opening it costs."),
        f("head_seq", "Long Int", default="0", read_only=1,
          description="How many saves this workbook has had. Version history "
                      "is not built; this is the counter it would hang off, "
                      "and it costs nothing to keep."),
    ],
)


# --------------------------------------------------------------------------- #
# What a document was filled from
#
# A quotation whose line items came off a spreadsheet has, until now, no memory
# of that: `pull` writes the rows and returns a count, and a month later nobody
# can say which sheet those prices were. That is the whole of what this row is
# for — one per (document, child table), replaced when it is filled again.
#
# `sheet` is `Data` and not a `Link`, deliberately. A link would block deleting
# the sheet and would take this row with it if the block were lifted, and the
# one moment this matters most is when the sheet is gone: "these lines came off
# Padel Pro estimator on the 3rd" is worth keeping when the estimator is not.
# --------------------------------------------------------------------------- #

doctype(
    "Sheet Feed",
    app="tenant",
    module="OneSheet",
    autoname="hash",
    title_field="sheet_title",
    search_fields="reference_doctype,reference_name,sheet_title",
    perms=READONLY_PERMS,
    track_changes=1,
    fields=[
        f("reference_doctype", "Link", options="DocType", reqd=1, in_list_view=1),
        f("reference_name", "Dynamic Link", options="reference_doctype", reqd=1,
          in_list_view=1),
        f("into", "Data", reqd=1, in_list_view=1,
          label="Child Table",
          description="The fieldname of the table these rows landed in. One "
                      "feed per table: a second pull into the same table "
                      "replaces the rows, so it replaces this too."),
        section("source", "Where it came from"),
        f("sheet", "Data", reqd=1,
          description="The File this was pulled from, by name. Data rather "
                      "than a Link so the record outlives the sheet."),
        f("sheet_title", "Data",
          description="What that sheet was called when the rows were pulled."),
        f("label", "Data", reqd=1,
          description="The named range. The contract between a sheet and the "
                      "document it fills."),
        column("outcome"),
        f("filled", "Int", read_only=1, description="Rows written."),
        f("skipped", "Small Text", read_only=1,
          description="Headings with no matching field, which were left out."),
        section("state", "Where it stands"),
        f("status", "Select", options="Following\nLocked", default="Following",
          in_list_view=1,
          description="Following: filling again replaces these rows. Locked: "
                      "the document is the record now and the sheet is "
                      "history, so a pull is refused until somebody unlocks "
                      "it."),
        f("pulled_on", "Datetime", read_only=1),
        f("pulled_by", "Link", options="User", read_only=1),
        f("locked_on", "Datetime", read_only=1),
        f("locked_by", "Link", options="User", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Documents
#
# A document is a `File`, the same way a sheet is — see `docs/WRITER.md`. The
# File row is its name, owner, folder, share, place in the bin and binding to a
# record; this holds the only thing a File cannot, which is the prose.
#
# Two representations of one document, and both are needed. `content` is the
# ProseMirror JSON the editor round-trips and is the source of truth. `html` is
# what that JSON renders to, written on every save, and it is what search, the
# preview, print, export and a mail body all read — none of which should be
# made to load an editor to find out what a document says.
#
# Reseamed from `frappe/writer`'s `Writer Document` (AGPL-3.0, © Frappe
# Technologies Pvt. Ltd.). Theirs stores a base64 Yjs update because its editing
# model is peer-to-peer CRDT over `wss://signal.frappe.cloud`; ours is a whole
# document saved by one writer at a time, for the reason `docs/SHEETS.md` gives
# about not adding a second runtime to a shard. So the columns are the same
# minus the CRDT ones, and the version table below replaces `Writer Version`.
# --------------------------------------------------------------------------- #
doctype(
    "Doc Body",
    app="tenant",
    module="OneDoc",
    autoname="field:doc",
    title_field="doc",
    search_fields="doc",
    perms=READONLY_PERMS,
    fields=[
        f("doc", "Data", reqd=1, unique=1, in_list_view=1,
          description="The File this prose belongs to, by name. Data and "
                      "unique rather than a Link so the row is addressable as "
                      "`Doc Body/<file>` — one statement to load, no filter."),
        f("content", "Long Text",
          description="The document as ProseMirror JSON: the source of truth, "
                      "and the only representation the editor reads back. "
                      "Replaced whole on every save."),
        f("html", "Long Text",
          description="What that JSON renders to, written on the same save. "
                      "Everything that is not the editor reads this one — "
                      "search, the preview, print, export, a mail body — so "
                      "none of them has to load an editor to find out what the "
                      "document says."),
        column("cb_body_size"),
        f("settings", "JSON",
          description="How the page is set: width, typeface, line spacing, and "
                      "whether it is locked against accidental typing. The "
                      "reader's choices about one document, not the "
                      "workspace's about all of them."),
        f("byte_size", "Int", read_only=1,
          description="Bytes of content plus html. What the storage meter "
                      "counts for a document, since it has no object behind "
                      "it."),
        f("head_seq", "Long Int", default="0", read_only=1,
          description="How many saves this document has had. `File Version` "
                      "rows point at it, which is how the history panel knows "
                      "whether what it is showing is the current text."),
    ],
)


# --------------------------------------------------------------------------- #
# Versions, for both of them
#
# One doctype and not three, because a version of a sheet, of a document and of
# a source file are the same row: a blob, whose file it belongs to, when it was
# taken, by whom, and whether a person named it. The three stores differ — a
# workbook is `codec.py`'s gzipped envelope, a document is ProseMirror JSON, a
# `.py` is its own bytes — and neither this row nor the module over it has to
# care, because restoring is handing the blob back to the store it came from.
#
# The policy over these rows is taken from `frappe/sheets`'
# `sheets/versioning/` (AGPL-3.0, © Frappe Technologies Pvt. Ltd.): snapshot on
# the first save, on N saves, or after T seconds of work; never prune what
# somebody named; thin the automatic ones on a tiered schedule so a year of
# editing is not a year of blobs. What was not taken is their op log, which
# exists because their save is incremental and ours is total.
# --------------------------------------------------------------------------- #
doctype(
    "File Version",
    app="tenant",
    module="OneStorage",
    autoname="hash",
    title_field="title",
    search_fields="file,title",
    perms=READONLY_PERMS,
    fields=[
        f("file", "Data", reqd=1, in_list_view=1,
          description="The File this is a version of, by name. Data rather "
                      "than a Link for the same reason the bodies are: the row "
                      "is written and read by name, and a Link would make "
                      "deleting the file a cascade nobody asked for."),
        f("kind", "Select", options="Sheet\nDoc\nText", reqd=1, in_list_view=1,
          description="Which store the payload goes back to. On the row rather "
                      "than derived from the File, so a version is readable on "
                      "its own — including after the file it came from is "
                      "gone. `Text` covers every file whose bytes are its own "
                      "— a `.py`, a `.md`, a `.txt` — where the payload is "
                      "simply the content and the store is the object."),
        f("title", "Data", in_list_view=1,
          description="What to call this version in the panel. A timestamp for "
                      "an automatic one; whatever somebody typed for a named "
                      "one."),
        f("manual", "Check", default="0", in_list_view=1,
          description="Somebody asked for this version by name. Never pruned, "
                      "and sorted above the automatic ones."),
        column("cb_version_body"),
        f("payload", "Long Text",
          description="The whole body as it stood, in whatever shape its store "
                      "reads. Restoring writes this back unchanged."),
        f("byte_size", "Int", read_only=1),
        f("at_seq", "Long Int", default="0", read_only=1,
          description="The `head_seq` of the body when this was taken. What "
                      "the panel compares against to say which version is the "
                      "one on screen."),
        f("saves", "Int", default="0", read_only=1,
          description="Saves between this version and the one before it. The "
                      "panel says '3 changes' rather than nothing at all."),
    ],
)


# --------------------------------------------------------------------------- #
# OneLegal
# --------------------------------------------------------------------------- #

doctype(
    "Legal Document Version",
    app="tenant",
    module="OneLegal",
    # The two fields that define it, and no third one holding their join.
    # `field:` needs a real fieldname and `name` is not one — a doctype named
    # that way throws "ID is required" the first time a version is stored,
    # which is the first time a clause changes rather than at install.
    autoname="format:{document}-{version}",
    title_field="title",
    search_fields="document,version",
    allow_rename=0,
    fields=[
        f("document", "Data", "Document", reqd=1,
          description="The document's key — terms, privacy, dpa."),
        f("title", "Data", "Title", reqd=1),
        f("version", "Data", "Version", reqd=1,
          description="revision.hash — see oneapp/onelegal/assemble.py."),
        f("revision", "Int", "Revision"),
        f("audience", "Select", "Audience", options="\ncustomer\nuser\nboth"),
        column("cb_lv_text"),
        f("html", "Text Editor", "As shown", read_only=1),
        f("text", "Long Text", "As hashed", read_only=1,
          description="The plain text the version's hash was taken over."),
    ],
    perms=READONLY_PERMS,
)

doctype(
    "Legal Acceptance",
    app="tenant",
    module="OneLegal",
    autoname="hash",
    fields=[
        f("document", "Data", "Document", reqd=1, in_list_view=1),
        f("version", "Data", "Version", reqd=1, in_list_view=1),
        f("stored_version", "Link", "Text agreed to", options="Legal Document Version"),
        f("party", "Select", "Party", options="Workspace\nUser", reqd=1,
          in_list_view=1),
        column("cb_la_who"),
        f("user", "Link", "Who", options="User", reqd=1, in_list_view=1),
        f("accepted_on", "Datetime", "When", reqd=1),
        f("address", "Data", "From address"),
        f("agent", "Small Text", "Browser"),
    ],
    perms=READONLY_PERMS,
)

# --------------------------------------------------------------------------- #
# Bound Record — a record a file is written about
#
# A document used to be bound to one record, and that binding was its
# attachment. Both halves of that stopped being true at once. A covering letter
# names the quotation *and* the customer *and* the project, so one is not
# enough; and a template is bound to a *kind* rather than to a record, which an
# attachment cannot express at all.
#
# So a file has a set of these, and the attachment goes back to meaning what it
# says: where the file is filed. A row with no `reference_name` is a template's
# slot — the doctype is known, the record is asked for when somebody starts
# from it.
#
# `key` is what a token names, and is why this is a row rather than a list of
# doctypes: a letter may be about two projects, and "project" and "project_2"
# have to stay apart when somebody swaps one of them.
#
# Its own doctype rather than a JSON column because the interesting query runs
# the other way — which documents mention this quotation — and a JSON column
# cannot answer that without reading every file in the workspace.
# --------------------------------------------------------------------------- #
doctype(
    "Bound Record",
    app="tenant",
    module="OneSpace",
    autoname="hash",
    fields=[
        f("file", "Link", "File", options="File", reqd=1, in_list_view=1,
          search_index=1,
          description="The document or workbook that reads this record."),
        f("key", "Data", "Key", reqd=1, in_list_view=1,
          description="What a token or a formula calls this source. Stable "
                      "across a record being swapped, which is the whole "
                      "point of it."),
        f("label", "Data", "Label",
          description="What the sidebar calls it. The doctype's name unless "
                      "somebody renamed it — two projects need telling apart."),
        column("cb_bound_record"),
        f("reference_doctype", "Link", "Kind", options="DocType", reqd=1,
          in_list_view=1, search_index=1,
          description="The record kind. Known on a template, where the record "
                      "itself is not."),
        f("reference_name", "Dynamic Link", "Record",
          options="reference_doctype", in_list_view=1, search_index=1,
          description="Empty on a template: the slot is declared and the "
                      "record is asked for when somebody starts from it."),
        f("idx_hint", "Int", "Order", default="0",
          description="Where it sits in the sidebar. The first source is the "
                      "one a bare token means."),
    ],
)
