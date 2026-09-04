"""Bringing a spreadsheet in, and being able to say what happened.

A source is a file; a plan is how its columns map; a run is one attempt, with a
step per doctype and an issue per row that did not make it. Identities are how a
second run recognises what the first one wrote.
"""

from .spec import column, doctype, f, section


# --------------------------------------------------------------------------- #
# Bringing a customer's data with them
#
# Every workspace that replaces something arrives with years of it, on a site
# somebody still uses. A one-shot script gets that wrong twice: it runs once,
# against a system that keeps moving, so the go-live is a night nobody works and
# a morning of typing in what changed.
#
# So this is an engine rather than a script, and the four doctypes below are its
# whole state. What makes it worth calling one:
#
# * **Idempotent.** Every source row's target is remembered in `Import Identity`,
#   so running it twice updates rather than duplicates, and a link resolves to
#   the row a previous step created.
# * **Incremental.** Each step keeps a watermark — the newest `modified` it has
#   seen — and asks the source only for what changed after it. Run it a month
#   before the cutover, run it again at midnight, and the second run is the
#   delta.
# * **Resumable.** A step that dies mid-way has already advanced its watermark
#   over what it committed, so the next run starts where it stopped rather than
#   at the beginning.
# * **Answerable.** Every row that failed is kept with its payload and its
#   error, so a bad import is a list to work through rather than a log to read.
# * **Rehearsable.** A dry run maps every row and writes nothing, which is the
#   only honest way to find out what a migration will do before it does it.
#
# It is deliberately not RUA-specific. A plan is data — steps, field maps, value
# maps — so the next customer arriving off their own Frappe site is a plan and
# no code at all.
# --------------------------------------------------------------------------- #
doctype(
    "Import Source",
    app="tenant",
    autoname="field:source_name",
    search_fields="base_url",
    states=[("Verified", "Green"), ("Never verified", "Gray"), ("Refused", "Red")],
    fields=[
        f("source_name", reqd=1, in_list_view=1,
          description="What this system is called to the people leaving it."),
        f("base_url", reqd=1, in_list_view=1,
          description="The site to read from, e.g. `https://old.example.com`. "
                      "No trailing slash and no path."),
        column("cb_source_auth"),
        # A Frappe API token pair. The secret is a Password field, which Frappe
        # keeps in its own encrypted store rather than on the row — so a copy of
        # this table is not a copy of the credential.
        f("api_key", reqd=1, description="From the source site's own user."),
        f("api_secret", "Password", reqd=1),
        section("sec_source_state", "Last checked"),
        f("status", "Select", options="Never verified\nVerified\nRefused",
          default="Never verified", read_only=1, in_list_view=1),
        f("verified_on", "Datetime", read_only=1),
        column("cb_source_state"),
        f("verified_as", read_only=1,
          description="Who the source site said we were. Worth reading: an "
                      "import runs as this user over there, and a key made "
                      "from an account with half the permissions imports half "
                      "the data without failing."),
        f("last_error", "Small Text", read_only=1),
    ],
)


doctype(
    "Import Step",
    app="tenant",
    istable=1,
    fields=[
        f("source_doctype", reqd=1, in_list_view=1,
          description="What to read on the source site."),
        f("target_doctype", reqd=1, in_list_view=1,
          description="What to write here. Usually an ERPNext or HRMS doctype: "
                      "the point of the move is that it stops being bespoke."),
        f("enabled", "Check", default="1", in_list_view=1),
        column("cb_step_shape"),
        # Target-keyed rather than source-keyed, because what is being built is
        # the target: read it top to bottom and it is the record you end up
        # with. Each value is one of
        #   {"from": "<source field>"}                       copy
        #   {"from": ..., "values": {...}, "default": "..."} copy through a map
        #   {"from": ..., "link": "<source doctype>"}        resolve to what an
        #                                                    earlier step made
        #   {"const": "..."}                                 the same every row
        f("field_map", "Code", options="JSON", reqd=1,
          description="What each target field is made of, keyed by target "
                      "fieldname. See `oneapp_core/importer.py`."),
        f("filters", "Code", options="JSON",
          description="Narrow what comes across, in Frappe's own filter shape. "
                      "Applied on the source site, so what is excluded is never "
                      "fetched."),
        # One row over there being many rows here — the second most common
        # shape a migration takes. A bespoke system that keeps a month of
        # attendance as one row a day holding an object keyed by employee is
        # not unusual; it is what a system with no reporting looks like from
        # the inside.
        # Files, which is the half of a migration people notice and nobody
        # writes down. A project's photographs, a party's logo, the scan behind
        # every compliance document — a system that arrives without them is a
        # database rather than the company's records.
        f("carry_files", "Check", default="0",
          description="Bring across everything attached to each row and attach "
                      "it here. One request per row and one download per file, "
                      "so it is opt-in per step."),
        f("carry_file_fields", "Small Text",
          description="Source fields that hold a path to a file rather than a "
                      "value, comma separated. The file is fetched and attached "
                      "here — for the picture somebody chose rather than "
                      "uploaded, which is attached to nothing over there."),
        f("fan_out", "Code", options="JSON",
          description='Where one source row is several records. '
                      '`{"from": "attendance_log", "shape": "map"}` makes one '
                      'record per key; `"list"` makes one per item. Each gets '
                      'the parent\'s fields with its own merged over them and '
                      '`__key` holding what it came in under.'),
        section("sec_step_state", "Where it got to"),
        # The whole incremental story, in one field. Advanced only over rows
        # that committed, so a step that dies half way resumes rather than
        # restarts — and never skips: it is the *oldest* possible safe point,
        # not the newest row seen.
        f("watermark", "Datetime", read_only=1, in_list_view=1,
          description="The newest `modified` this step has taken across. The "
                      "next run asks the source only for what changed after "
                      "it. Clear it to import everything again."),
        column("cb_step_state"),
        f("last_run", "Link", options="Import Run", read_only=1),
        f("notes", "Small Text"),
    ],
)


doctype(
    "Import Plan",
    app="tenant",
    autoname="field:plan_name",
    search_fields="source,space_code",
    fields=[
        f("plan_name", reqd=1, in_list_view=1),
        f("source", "Link", options="Import Source", reqd=1, in_list_view=1),
        column("cb_plan_scope"),
        f("space_code", description="Which space this fills. For the record: "
                                    "the import writes doctypes, not screens."),
        f("is_active", "Check", default="1", in_list_view=1),
        section("sec_plan_steps", "Steps"),
        # Order is the dependency order, and it is the author's to get right:
        # a step that resolves a link to something a later step creates will
        # find nothing, and say so as an issue rather than guessing.
        f("steps", "Table", options="Import Step",
          description="In dependency order — parties before the invoices that "
                      "link to them. A link that points at a step not yet run "
                      "is an issue on the row, not a silent blank."),
    ],
)


doctype(
    "Import Run Step",
    app="tenant",
    istable=1,
    fields=[
        f("source_doctype", read_only=1, in_list_view=1),
        f("target_doctype", read_only=1, in_list_view=1),
        f("status", "Select",
          options="Queued\nRunning\nDone\nFailed\nSkipped",
          default="Queued", read_only=1, in_list_view=1),
        column("cb_run_step_counts"),
        f("seen", "Int", default="0", read_only=1, in_list_view=1),
        f("created", "Int", default="0", read_only=1, in_list_view=1),
        f("updated", "Int", default="0", read_only=1, in_list_view=1),
        f("failed", "Int", default="0", read_only=1, in_list_view=1),
        column("cb_run_step_marks"),
        f("watermark_from", "Datetime", read_only=1,
          description="Where this step started reading. Empty is everything."),
        f("watermark_to", "Datetime", read_only=1),
        f("error", "Small Text", read_only=1),
    ],
)


doctype(
    "Import Run",
    app="tenant",
    autoname="format:IMP-{YY}{MM}-{#####}",
    search_fields="plan,status",
    states=[
        ("Queued", "Gray"),
        ("Running", "Blue"),
        ("Done", "Green"),
        ("Failed", "Red"),
        ("Cancelled", "Gray"),
    ],
    fields=[
        f("plan", "Link", options="Import Plan", reqd=1, in_list_view=1),
        f("status", "Select",
          options="Queued\nRunning\nDone\nFailed\nCancelled",
          default="Queued", read_only=1, in_list_view=1),
        column("cb_run_mode"),
        # The rehearsal. Everything happens — fetch, map, resolve, validate —
        # and nothing commits. It is the only honest way to find out what a
        # migration will do, and it is why the counts below are meaningful on a
        # run that changed nothing.
        f("dry_run", "Check", default="0", in_list_view=1,
          description="Map everything and write nothing. The counts and the "
                      "issues are real; the records are not."),
        f("started_on", "Datetime", read_only=1),
        f("finished_on", "Datetime", read_only=1),
        section("sec_run_steps", "Steps"),
        f("steps", "Table", options="Import Run Step", read_only=1),
        section("sec_run_totals", "Totals"),
        f("total_seen", "Int", default="0", read_only=1),
        f("total_created", "Int", default="0", read_only=1),
        column("cb_run_totals"),
        f("total_updated", "Int", default="0", read_only=1),
        f("total_failed", "Int", default="0", read_only=1),
        f("error", "Small Text", read_only=1),
    ],
)


doctype(
    "Import Identity",
    app="tenant",
    autoname="hash",
    # Written once per source row and then read on every later link. Change
    # tracking would file a Version per row of a migration, which is a table
    # the size of the migration recording that a machine did what it was asked.
    track_changes=0,
    search_fields="source_name,target_name",
    fields=[
        # The unique key, and the reason a second run updates rather than
        # duplicates. Not the target's own naming: a source row whose name is a
        # hash and whose target is `field:` named has no other way back.
        f("plan", "Link", options="Import Plan", reqd=1, in_list_view=1),
        f("source_doctype", reqd=1, in_list_view=1),
        f("source_name", reqd=1, in_list_view=1),
        column("cb_identity_target"),
        f("target_doctype", reqd=1, in_list_view=1),
        f("target_name", reqd=1, in_list_view=1),
        f("last_seen", "Datetime", read_only=1),
    ],
)


doctype(
    "Import Issue",
    app="tenant",
    autoname="hash",
    track_changes=0,
    search_fields="source_name,error",
    states=[("Open", "Red"), ("Resolved", "Green")],
    fields=[
        f("run", "Link", options="Import Run", reqd=1, in_list_view=1),
        f("source_doctype", in_list_view=1),
        f("source_name", in_list_view=1),
        column("cb_issue_state"),
        f("status", "Select", options="Open\nResolved", default="Open",
          in_list_view=1),
        f("error", "Small Text", read_only=1, in_list_view=1),
        section("sec_issue_payload", "The row"),
        # Kept whole. A failed import row is worth exactly as much as the thing
        # that failed to become — without it, fixing one means going back to a
        # source site that has since moved on.
        f("payload", "Code", options="JSON", read_only=1,
          description="What the source said, as it said it."),
        f("mapped", "Code", options="JSON", read_only=1,
          description="What we made of it before it was refused."),
    ],
)
