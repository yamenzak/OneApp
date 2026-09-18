# Collections

**Reference data is doctypes. Facts are not.** That split is the one decision
everything else in this module follows from, and it is the only module in the
product that steps outside Frappe's Document machinery on purpose.

## Owned — the documents

| Doctype | What it is |
| --- | --- |
| `Transit Agency` | Who runs the service. `agency_name`, `emoji`, `agency_key`, `timezone`, `url`, `feed`. |
| `Transit Line` | A route. `short_name`, `line_name`, `agency`, `line_key`, `status`, `mode`, `colour`, `emoji`, `marker_shape`, `feed`, `shape`. |
| `Transit Stop` | A place a vehicle calls. `stop_name`, `stop_code`, `stop_key`, `latitude`, `longitude`, `place`, `parent_stop`, `zone`. |
| `Transit Vehicle` | A bus, a tram, a train. `vehicle_key`, `label`, `mode`, `seats`, `standing`, `capacity`, `agency`. |
| `Transit Source` | Where the data comes from, with its credentials. `kind`, `format`, `precedence`, the folder or endpoint, `every_minutes`, `last_run`, `watermark`. |
| `Transit Feed` | One delivery from a source. `status`, `received_on`, `origin`, `format`, `file`, and the three counts. |
| `Transit Claim` | What a source *said* about an entity. `entity`, `natural_key`, `source`, `verdict`, `contested`, `precedence`, `record`, `differs`, `claimed`. |
| `Transit Marker Style` | How a mode is drawn. `mode`, `shape`, `emoji`. |
| `OneMobility Settings` (single) | `hot_days`, `frozen_days`. |

Hundreds to low thousands of rows each, and every one is something a person
opens, comments on, shares, follows, assigns and prints — so they get the whole
record surface for free, which is the entire reason One exists.

## Not doctypes — the facts

A Stop Time is not a document. A mid-size operator's timetable period is
millions of them, and `get_doc().save()` per row is not slow, it is impossible.

The arithmetic, once, because it is the whole argument. 500 vehicles reporting
every 15 seconds over an 18-hour day is **2.2 million observations a day**. As
documents that is a controller instantiation, a validation pass, a permission
check and a `modified` stamp each, inserted one at a time — four hours of
continuous CPU, to store data nobody will ever open individually. As plain
rows — a `BIGINT` key, a vehicle id, a timestamp and two scaled integers —
it is **~110 MB and a few seconds**.

So facts live in **plain tables this module creates and writes in bulk**:
`CREATE TABLE` in a patch, batched `INSERT`, `frappe.db.sql` behind a
whitelisted endpoint that returns rows **already grouped**. No `name` column,
no controller, no Document class.

What is given up is exactly what nobody wants on a GPS ping: per-row
permissions, comments, the timeline, versions, assignment. **Permission lives
one level up**, on the Vehicle and the Line, which are documents.

## The four tiers

| tier | where | holds | answers |
| --- | --- | --- | --- |
| hot | MariaDB, partitioned by day | raw rows, ~30 days | anything, at full grain |
| warm | R2, one object per vehicle per day | the rolled track | playback, instantly |
| frozen | R2, one Parquet file per day | the raw rows again | a question nobody anticipated |
| aggregate | MariaDB, never expires | per line/stop/hour counts and **percentiles** | every chart, every long range, every forecast |

**Long-range questions are aggregate questions.** Nobody asks where vehicle 412
was at 14:23:07 last March; they ask what punctuality on line 12 was last
quarter. So the small answer is kept forever and the large one is not.

**Percentiles, not means** — a mean cannot be turned into "seven times in ten",
which is what the forecast needs.

The hot table is **partitioned by day**, so retiring a month is `DROP
PARTITION` rather than a `DELETE` of sixty million rows.

## The two windows are the workspace's

`hot_days` and `frozen_days` on `OneMobility Settings`, both Ints, both empty
by default — and **empty means the number declared in `model.py`**. An unset
Int and a deliberate nought are the same value in Frappe, and a workspace must
not be able to throw its own history away by clearing a field.

`shared/facts` reads them by those exact field names off the Single each table
declares, so the wiring **is** the doctype.
