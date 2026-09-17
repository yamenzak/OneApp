# Integrations

## Frappe — and the one place this module steps outside it

**The documents are ordinary.** Line, Stop, Vehicle, Agency, Source, Feed,
Claim and the Settings single are Frappe doctypes with the whole record surface
— permissions, the timeline, saved views, comments, assignment.

**The facts are not.** Plain tables created in a patch, written by batched
`INSERT`, read by `frappe.db.sql` behind whitelisted endpoints that return rows
already grouped. No `name`, no controller, no Document class.

Nothing else in this product does that, and `collections.md` has the arithmetic
that earns it. The thing to hold onto: **permission lives one level up**, on
the Vehicle and the Line.

## ERPNext and HRMS

**Nothing.** `requires_apps` is empty, which is deliberate and is what makes
this space saleable to a transport authority who wants a viewer and not an ERP.
A bare site carries it.

## The open standards

**GTFS** and **GTFS-Realtime** — `gtfs.py`, `gtfsrt.py`. The two most
transport authorities publish.

**VDV** — `vdv.py`, `vdv301.py`, `vdv452.py`, `vdv457.py`. The German family,
and README §5a is the shelf plus the column nobody else writes down.

`sniff.py` decides which arrived, so a source does not have to declare its
format correctly to work.

## Cloudflare R2

Two of the four tiers. **Warm** is one object per vehicle per day, already in
the playback format. **Frozen** is one Parquet file per day.

R2 charging no egress is what makes fetching a day's objects on every scrub an
unremarkable cost rather than a bill.

**`cold/` is not this.** `lifecycle/cold.py`'s prefix is a whole workspace's
escrow copy for the dunning ladder, promoted from a backup. Frozen observations
are **live data in a cheaper place** — same bucket, different mechanism, and
conflating them would put a customer's working history behind a
restore-from-archive flow.

## OneCloud (`onestorage`)

Every feed file lands in the Drive as a `File`, so a delivery is auditable by
opening it. Frozen data **counts against the workspace's storage quota** — it
is cheaper, not free, and the meter should say so rather than hiding it.

## The engine (`onespace`)

* **`basemap.py`** — where a map gets its ground. The map *view type* is the
  engine's; what is here is the network drawn on it.
* **Two `component` screens** — the map with a clock, and the aggregate tier as
  plots.
* **`facets.py`** answers `offered`, which is the engine's one vocabulary for
  narrowing a screen (README §3c).
* **`shared/facts`** is the bulk-table helper, and it reads the two retention
  windows off the Single by field name.
* **README §8** lists what the engine was missing when this space was built and
  what it now has — every one of those is a general capability, not a transit
  one.

## OneCalendar

Nothing. A vehicle's day is not a diary entry.

## OneLegal

`legal.py` is the Datenschutz clause, and README §9 is the argument behind it:
what an operator who thinks their positional data is treasure needs to be told,
and what `lifecycle.forget_everything` is for.

## OneAI

`ai.md`.
