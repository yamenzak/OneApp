# OneMobility

A transport authority delivers timetables as files and vehicle positions as a
feed, and then reads both in a spreadsheet. OneMobility is where they look at
them instead: a live map of every vehicle, the network drawn on it, and a
scrubber that runs the same map backwards to any moment it has data for.

The sentence that sells it is not "beautiful charts". It is **"here is why the
12 ran late at 07:40 last Tuesday"** — the same screen, a different clock.
Nobody in this market does time travel well, and everybody has charts.

Germany first, through VDV. That is where the customers are, and it is a market
that publishes its formats. It is not where the model comes from — see below.

**Generally available.** RUA was one company's system and could take their
vocabulary and their colours. This one is enabled from the marketplace by
anybody, so it says Line and Stop, not whatever the first customer says, and it
has to survive people who do not work the way that customer does.

---

## 1. The one decision everything else follows from

**The internal model is GTFS's, and every format is an importer into it.**

Model on VDV's entities and we have built a German product that needs rewriting
the first time somebody in Vienna asks. Model on GTFS's — agency, route, trip,
stop, stop time, shape, calendar — and VDV 452 is an importer, GTFS is an
importer, NeTEx is an importer, and "support the other formats later" is a
plan rather than a rewrite.

The same holds on the live side, and more strongly: VDV 454, GTFS-Realtime and
SIRI are three spellings of the same four facts — **where a vehicle is, when it
is due, how full it is, how late it is**. A normaliser per dialect, one model
behind them.

GTFS is not chosen because it is better designed. It is chosen because it is
the *intersection*: every other format can be expressed in it without loss of
anything a screen draws, and it is the one an integrator already knows.

Two things to be honest about. VDV 452 carries planning concepts GTFS has no
word for — vehicle duties, blocks, driver rosters — and those are dropped on
import rather than modelled, because nothing we draw reads them. And the VDV
specifics below are written from a working understanding, not from the
standard: **read the actual spec before writing the parser**, and correct this
file when it disagrees.

---

## 2. The nouns

Reference data, which a person opens and talks about:

| | |
|---|---|
| **Source** | Where feeds come from — an SFTP host, an upload folder, an endpoint, a socket. A workspace connects several. |
| **Feed** | One delivery from one source at one moment. Everything traces back to a feed, which is what makes a wrong number answerable. |
| **Agency** | Who runs the service. |
| **Line** | What a rider calls "the 12". GTFS says route; riders and staff say line, so we say line. |
| **Stop** | A place a vehicle serves, with a position. Parent stations included. |
| **Vehicle** | The physical thing, with its capacity. |
| **Service Day** | Which pattern runs on which dates — GTFS's calendar, flattened. |

Facts, which nobody opens and everybody aggregates:

| | |
|---|---|
| **Trip** | One run of one line on one day. Millions per year. |
| **Stop Time** | A trip's arrival and departure at one stop. Tens of millions. |
| **Shape point** | The drawn geometry of a route. |
| **Observation** | Where a vehicle was, how full, how late, at a time. Tens of millions per day at 1 Hz. |

The line between the two tables is the architecture, and §3 is why.

---

## 3. Reference data is doctypes. Facts are not.

A Line, a Stop, a Vehicle, an Agency: hundreds to low thousands of rows, and
every one of them is something a person opens, comments on, shares, follows,
assigns and prints. Those are doctypes, and they get the whole record surface
for free — permissions, the timeline, saved views, the lot. That is the entire
reason OneSpace exists and OneMobility should not reinvent an inch of it.

A Stop Time is not a document. A single mid-size operator's timetable period is
millions of them, and `get_doc().save()` per row is not slow, it is impossible.
The arithmetic is worth writing down once, because it is the whole argument.

Take 500 vehicles reporting every 15 seconds over an 18-hour service day —
which is what real feeds do; 1 Hz is a pessimistic bound, not a normal rate.
That is **2.2 million observations a day**.

As doctypes: every row is a controller instantiation, a validation pass, a
permission check, a `modified` stamp and possibly a `tabVersion` row, inserted
one at a time because `save()` does not batch. Call it 150 a second on a small
shard and the day's writes need four hours of continuous CPU — to store data
nobody will ever open individually. The row itself is mostly overhead too: a
`varchar(140)` primary key that every secondary index carries a copy of, plus
ten metadata columns, so a GPS ping costs several hundred bytes of bookkeeping
to hold sixteen bytes of fact.

As plain rows: a `BIGINT` key, a vehicle id, a timestamp and two scaled
integers for the position — about 50 bytes with its index, written by
multi-row `INSERT` at tens of thousands a second. The same day is **~110 MB and
a few seconds of work**, arriving in batches of a few hundred. At a 30-day
retention window that is a steady state of three or four gigabytes, which is an
unremarkable table.

So it is not heavy data. It is data that becomes heavy the moment it is a
Document, and the weight is entirely Frappe's machinery rather than the facts.

Facts therefore live in **plain tables that OneMobility creates and writes in
bulk**, outside that machinery, read only through an aggregate API. Concretely:
`CREATE TABLE` in a patch, batched `INSERT`, and `frappe.db.sql` with a
hand-written query behind a whitelisted endpoint that returns rows already
grouped. No `name` column, no controller, no Document class.

What is given up is exactly what nobody wants on a GPS ping: per-row
permissions, comments, the timeline, versions, assignment. Permission lives one
level up, on the Vehicle and the Line, which are documents.

Why not a real analytics store — ClickHouse, Timescale, DuckDB over Parquet on
R2? Because a second service per tenant is a second thing to provision, back
up, restore, bill and page somebody about, and our shard model has no room for
one. A partitioned MariaDB table rides the site backup, the cold-storage
lifecycle and the restore path we already built, at zero new operational cost.

That is a decision with an expiry date, and the way to keep it cheap is to make
the read path an **aggregate API and never a query builder**: screens ask
"occupancy by hour for line 12 in March", not for rows. The day a customer's
volume outgrows MariaDB, the endpoint is reimplemented and no screen changes.
Writing screens against raw rows is what would make that swap a rewrite.

---

## 4. Playback is an object, not a query

The obvious build of a scrubber queries the fact table per frame, and it is
unusable: scrubbing is a hundred queries a second over the largest table.

Instead, a nightly job rolls each vehicle's day into **one compressed track
object per vehicle per day**, in R2 next to everything else OneStorage holds —
a delta-encoded array of time, position, occupancy and delay. Playback fetches
the day and scrubs entirely in the browser. 43 million rows become a few
thousand objects, a scrub costs no query at all, and the raw rows behind them
become deletable.

Live mode is the socket. Playback is the object. **They are one screen with two
clocks**, and that is the design worth protecting: two renderers would drift
into two products, and the whole pitch is that they are the same view.

---

## 5. Four doors, one pipeline

A workspace connects any of:

* **Upload** — drag a folder of files in, through OneStorage. The demo path,
  and the one a manager tries first.
* **SFTP** — how VDV planning data actually arrives. A host, a key, a folder, a
  schedule.
* **HTTP** — poll an endpoint, or receive a webhook.
* **Socket** — a subscription that pushes positions. VDV 453/454's real-time
  interfaces, GTFS-Realtime, SIRI.

Behind all four is **one pipeline**: fetch → parse → normalise → resolve →
commit, with a watermark. That is `onespace/importer.py`, which already exists,
is already idempotent, incremental, resumable, answerable and rehearsable, and
was deliberately written as an engine over a *plan* rather than as RUA's script.
A source is a plan. If OneMobility writes a second importer, something has gone
wrong.

The one addition it needs is a **streaming** mode: the existing engine assumes a
finite fetch, and a socket has no end. That is a source that appends to a buffer
and commits on a timer, reusing the same normalise and resolve steps.

---

## 6. Duplicates are a conflict, not magic

"Connect all your sources and the system smartly handles duplicates" is the
right feature and the wrong sentence. Software that silently drops one of two
disagreeing numbers is software nobody trusts twice, and in this market the
disagreement is often the *interesting* part — the planned timetable says 07:38
and the vehicle says 07:44.

So: every entity carries a **natural key** from its feed — agency + line id,
stop id, trip id + service date — and two sources claiming one key is a
recorded conflict. The customer sets **precedence per source**, the winner is
what screens draw by default, and the loser is kept and visible. A stop that
three sources agree on and one disagrees with says so.

That is also the honest version of the "select all sources" filter: it is not
merging, it is choosing whose answer to draw, and it can always show you the
others.

Route completion and stop generation — a vehicle stopping somewhere no feed
declares a stop — belong here too, as an **inferred** source with the lowest
precedence, never silently promoted into the network. An inferred stop is drawn
differently and can be accepted into the real network by a person.

---

## 7. The map, and the two different things people call one

**A map view** is a view type: pins over a `Geolocation` field, beside list,
board, gantt, calendar and tree. Any doctype with a position gets one — stops,
depots, incidents, and every future space's own records. That belongs in
**OneSpace**, not here, and OneMobility is simply its first customer. Building
it inside OneMobility is how it ends up RUA-shaped and unusable by anyone else.

**The live network screen** is not a view type. Moving vehicles, route lines
coloured by occupancy or delay, a time scrubber, a source filter and a legend
is a bespoke surface, and it is the first honest use of the manifest's
`component` escape hatch. Conflating the two is the mistake to avoid: one is an
engine feature that must stay generic, the other is a product that must not.

Rendering:

* **MapLibre GL JS**, BSD-3. Permissive, so it is a dependency like
  `frappe-gantt` and not a vendoring with AGPL obligations. WebGL, which is what
  makes a thousand moving markers possible at all.
* **Protomaps `.pmtiles`, served from our own R2.** One file per region, no
  per-tile requests to anybody, and a basemap we can style to stop it looking
  like raw OSM. It is also the privacy answer: with a third-party tile provider,
  every pan and zoom tells them which city a customer is watching, and the tile
  requests themselves leak the extent of a fleet.
* Routing, when it is needed, is OSRM or Valhalla over an OSM extract — **not**
  the OSM API, which is an editing interface and must not be used for this.

---

## 8. What the engine is missing

In the order it blocks:

1. **A map view type**, over `Geolocation`, in `lib/screen/viewTypes.js` and a
   `MapBody` beside the other bodies.
2. **A screen body over an aggregate API.** Every body we have reads a list of
   documents. A body that reads grouped numbers has no precedent, and it is what
   every chart on the dashboard needs once the source is a fact table.
3. **Time-series charts** that survive a hundred thousand points — decimation in
   the query, not in the browser.
4. **A source-connection surface.** Host, key, schedule, last run, what it
   brought. Settings-shaped but per space, and a space cannot contribute a
   settings tab today.
5. **A component screen that is a real product surface.** The escape hatch
   exists and nothing has used it in anger.

None is a reason to wait; they are the order to build in.

---

## 9. Datenschutz, and the operator who thinks their data is treasure

Two different fears, and only one of them is GDPR.

The GDPR one is mostly misplaced: a vehicle's position is not personal data,
timetables are published open data, and automatic passenger counts are
aggregates. What a German authority's procurement actually wants is EU region, a
signed DPA, a named subprocessor list and a deletion SLA — all of which OneSpace
already generates.

The real fear is commercial. Load factors and route profitability are what a
rival would want before bidding on the same tender, so what they are worried
about is **us**. Client-side-only and end-to-end encryption are not available —
duplicate resolution, history, peak-hour analysis, route completion and playback
are all server-side computation over accumulated data, and any scheme that
blinds the server kills every one of them.

What is available, and is a better answer:

* **Access transparency.** Support cannot reach a workspace by default. The
  customer grants access for a fixed number of hours with a stated reason,
  every action under it lands in a log *they* read, and they are mailed when it
  is granted and when it is used. We cannot say we cannot see it; we can say we
  cannot see it quietly. Today support arrives as Administrator holding System
  Manager, always on and unlogged, which is the gap.
* **Hold less.** Raw observations expire on a window the customer chooses;
  rolled tracks and aggregates persist. Simultaneously a privacy answer, a cost
  answer and a speed answer.
* **A site per customer**, which is already true — own database, own R2 prefix,
  not a tenant column in a shared table like most of the comparable products.
* **No subprocessor sees it**: self-hosted tiles, and AI off unless enabled.
* **Export and hard-delete, with a receipt.** "Treasure" is often lock-in fear
  in a better suit.
* **Their own cloud**, priced as enterprise, for the one who still says no. The
  licence permits it.

Encryption at rest is worth having and must be sold as "a stolen disk is
useless", never as protection from us — if the site can decrypt, so can root,
and a technical buyer will catch the overclaim.

---

## 10. What this is not

* Not a planning tool. It reads timetables; it does not build them.
* Not an AVL system. It renders somebody else's telemetry and does not talk to
  vehicles.
* Not a passenger app. The audience is the operator's own staff.
* Not a general BI tool. Charts are over transit's nouns, and a customer who
  wants arbitrary pivots over arbitrary data wants OneSheet.

---

## 11. Stages

Each ships something a person can look at.

1. **The model and one importer.** Doctypes for the reference nouns, the fact
   tables, and GTFS static from an upload — GTFS before VDV because the sample
   data is abundant and it proves the model is not VDV-shaped.
2. **The map view type**, in the engine, over Geolocation. Stops on a map, and
   every other space gets it too.
3. **VDV 452 over SFTP.** The real acquisition path, on the pipeline stage 1
   proved.
4. **The network screen, static.** Lines drawn from shapes, coloured, filtered,
   with a legend. No live data yet, and already a demo.
5. **Live.** A socket source, the observation table, vehicles moving.
6. **The scrubber.** The nightly roll-up, the day objects, and one screen with
   two clocks.
7. **Analysis.** Peak hours, punctuality, occupancy over time — the aggregate
   API and the charts on it.
8. **Sources, plural.** Precedence, conflicts, inferred stops, the connection
   surface.

Stages 1–4 are a sellable demo. Stages 5–6 are the product. Stage 7 is what
renews it.

---

## 12. The fixture

RUA is being dismantled, and it is currently what `scripts/dev.sh seed` builds
and what most of the browser suite reads. **OneMobility should become the
fixture that replaces it**, from stage 1 onward, rather than us building a
second fixture and throwing it away.

That is a constraint on stage 1, not an afterthought: the seed must produce a
small, real, checked-in GTFS feed — a handful of lines, a few dozen stops, a
day of synthetic observations — deterministic enough that a screenshot is
comparable between runs.

Test data is not the problem it looks like. GTFS feeds are published openly by
most German authorities and by aggregators; VDV 452 samples are scarcer and
will likely have to come from a customer or from an open repository, which is
one more reason stage 1 is GTFS.

---

## 13. The mark

The brand mark is a sky-to-deep-blue diamond with a white hub. It used to carry
the family's twin `||` cuts, which were removed from every app mark for good
reasons (`scripts/gen_brand.py`, `uncut`), and the removal was right here too:
rendered side by side, the cuts slice straight through the hub and read as a
cracked tile rather than as route lines, and below 48px they are noise.

But what is left is generic — a diamond with a dot is a map pin, and there are a
thousand of those. The fix is not to restore the mask: it is to draw the routes
as **positive shapes**, a line through the diamond with two stop dots, so the
mark says transit at 20px instead of saying location. `CUT_IS_THE_MARK` in the
generator is the precedent for a mark whose lines are the drawing.

Small, and worth doing before this space is ever shown to anybody.

---

## 14. Open questions

* Does the first customer's VDV delivery match the spec, or their reading of it?
  Every integration project in this market turns on that answer.
* What retention window is defensible as a default — 30 days of raw
  observations, or 90?
* Is occupancy real (APC hardware) or estimated? It changes what the colour on a
  route line is allowed to claim.
* Does the fact table live in the tenant's own database, or in a separate one
  per workspace? The second is better for backup size and restore time and is a
  provisioning change.
