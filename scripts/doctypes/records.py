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
# record. What these three add is the only thing a File cannot hold, which is a
# grid.
#
# A row per cell rather than one JSON blob per workbook, which is where this
# parts company with Frappe Sheets. The reason is the read-back: a named range
# names a rectangle, and pulling it into a document's child table has to be a
# query rather than a megabyte of JSON walked in Python. It also makes a cell's
# history Frappe's own rather than a second history of our own devising.
# --------------------------------------------------------------------------- #
doctype(
    "Sheet Tab",
    app="tenant",
    autoname="hash",
    title_field="tab_name",
    search_fields="sheet,tab_name",
    perms=READONLY_PERMS,
    fields=[
        f("sheet", "Link", options="File", reqd=1, in_list_view=1,
          description="The File this tab belongs to. A sheet with no tab row "
                      "has one tab called Sheet1, because a workbook always "
                      "has at least one and storing that fact would be storing "
                      "a default."),
        f("tab_name", "Data", reqd=1, in_list_view=1,
          description="What the tab is called, and what a formula in another "
                      "tab refers to it by."),
        f("position", "Int", default="0", in_list_view=1,
          description="Left to right. Not the creation order: tabs are "
                      "dragged."),
        column("cb_tab_frozen"),
        f("frozen_rows", "Int", default="0",
          description="How many rows stay put when the grid scrolls."),
        f("frozen_columns", "Int", default="0"),
        f("column_widths", "Long Text",
          description="A JSON map of column letter to pixels, for the ones "
                      "somebody has resized. Absent means the default, so a "
                      "fresh sheet stores nothing."),
        f("row_heights", "Long Text"),
    ],
)


doctype(
    "Sheet Cell",
    app="tenant",
    autoname="hash",
    title_field="ref",
    search_fields="sheet,ref",
    perms=READONLY_PERMS,
    fields=[
        f("sheet", "Link", options="File", reqd=1, in_list_view=1),
        f("tab", "Data", reqd=1, in_list_view=1,
          description="By name and not by link. A tab is renamed often and a "
                      "cell must follow it without a thousand rows being "
                      "rewritten — the rename updates this column in one "
                      "statement."),
        f("ref", "Data", reqd=1, in_list_view=1,
          description="A1 notation, upper case. The column letter and the row "
                      "number, which is what a person types and what a formula "
                      "carries."),
        column("cb_cell_value"),
        # The two-column heart of the whole design. See §3 and §5 Stage 1 of
        # `docs/SHEETS.md`: every formula engine for Python is copyleft, so the
        # server never evaluates anything — it reads what the browser worked
        # out. A print format, a report and the read-back all want `value`.
        f("raw", "Long Text",
          description="What was typed. `=A2*B2*C2` for a formula, the literal "
                      "otherwise."),
        f("value", "Long Text",
          description="What that came to, worked out in the browser and stored "
                      "here. The server never evaluates a formula — it reads "
                      "this. A print format, a report and a read-back all use "
                      "it, and none of them has a browser."),
        f("kind", "Select", options="\n".join(["", "number", "text", "date", "bool", "error"]),
          description="What `value` is, decided when it was computed. Saves "
                      "every reader guessing from a string, and is what lets a "
                      "read-back put a number in a Currency field."),
        f("format_json", "Long Text",
          description="Bold, alignment, number format, fill. JSON because it "
                      "is a bag of presentation and none of it is queried."),
    ],
)


doctype(
    "Sheet Range",
    app="tenant",
    autoname="hash",
    title_field="label",
    search_fields="sheet,label",
    perms=READONLY_PERMS,
    fields=[
        f("sheet", "Link", options="File", reqd=1, in_list_view=1),
        f("label", "Data", reqd=1, in_list_view=1,
          description="What the range is called. A formula may use it, and the "
                      "read-back names it — this is the contract between a "
                      "sheet and the document it feeds."),
        f("tab", "Data", reqd=1),
        f("ref", "Data", reqd=1, in_list_view=1,
          description="`A1:G40`. The rectangle, in the same notation a cell "
                      "uses."),
    ],
)
