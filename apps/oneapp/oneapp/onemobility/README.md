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

## 3a. Four tiers, and why the old data can leave the database

Frappe has no answer for this, and that is fine: it has no answer *for
documents*, and observations are not documents. Having stepped outside the
Document machinery in §3, nothing constrains where the rows live.

The reframing that makes it easy: **long-range questions are aggregate
questions.** Nobody asks where vehicle 412 was at 14:23:07 in March last year.
They ask what punctuality on line 12 was last quarter. So the small answer is
kept forever and the large one is not.

| tier | where | holds | answers |
|---|---|---|---|
| hot | MariaDB, partitioned by day | raw rows, ~30 days | anything, at full grain |
| warm | R2, one object per vehicle per day | the rolled track | playback, instantly |
| frozen | R2, one Parquet file per day | the raw rows again | a question nobody anticipated |
| aggregate | MariaDB, never expires | per line/stop/hour counts and **percentiles** | every chart, every long range, every forecast |

The aggregate tier is the one that makes the rest affordable. A year of "trips,
mean delay, mean occupancy, per line per stop per hour" is tens of thousands of
rows — a rounding error beside the raw, and it is what every chart on every
dashboard actually reads.

Two different things get called "load on demand" and they are not the same:

* **Playing back a specific past day** needs no rehydration at all. The day's
  track objects are already the playback format (§4), so the browser fetches
  them from R2 and scrubs. This is the common case and it is instant.
* **A novel question over frozen raw** — the rare case — is DuckDB reading
  Parquet on R2 directly, or a date range pulled back into a temporary table for
  one report. Either way it is minutes, on request, and it does not have to be
  built until somebody asks.

Two details that decide whether this works in practice. The hot table must be
**partitioned by day**, so retiring a month is `DROP PARTITION` — instant —
rather than a `DELETE` of sixty million rows, which locks the table and leaves
it bloated. And R2 charges no egress, which is what makes fetching a day's
objects on every scrub an unremarkable cost rather than a bill.

One thing this is not: `lifecycle/cold.py`'s `cold/` prefix is a whole
workspace's escrow copy for the dunning ladder, promoted from a backup. Frozen
observations are live data in a cheaper place. Same bucket, different
mechanism, and conflating them would put a customer's working history behind a
restore-from-archive flow.

Frozen still counts against the workspace's storage quota. It is cheaper, not
free, and the meter should say so rather than hiding it.

## 3b. The four aggregates, and how a stop gets a number

The tier that stays is not one table. `observation` is raw and rolls into two
of them; a third is derived rather than rolled, and rolls into a fourth.

| table | grain | rolled from | answers |
|---|---|---|---|
| `serviceHour` | line, hour, weekday | `observation` | how the network runs |
| `vehicleDay` | vehicle, line, day | `observation` | how one bus runs |
| `stopEvent` | one visit, hot 30 days | *inferred*, see below | what happened at a stop |
| `stopHour` | stop, line, hour, weekday | `stopEvent` | what a stop does |

**Why vehicle is a second table and not a fourth column on the first.** Putting
`vehicle` in `serviceHour` multiplies it by the size of the fleet: a mid-size
operator's line-and-hour tier is four thousand rows a year and its
line-hour-and-vehicle tier is four million, on the tier whose whole
justification is that a year of it is a rounding error. Per vehicle per *day*
is a hundred and eighty thousand, and it answers every question anybody asks
about a vehicle. So `shared/facts.py` takes a list of roll-up plans rather than
one, which is the normal shape for a raw tier: two aggregates at two grains,
not one aggregate at a compromise.

**Why a stop event is inferred.** Nothing else here is. A feed reports
"vehicle 41 is at 52.5219, 13.4132" and never "vehicle 41 is serving
Alexanderplatz", and without that second sentence a stop has no history at all
— no dwell, no headway, no answer to what it does on a Saturday. GTFS has
`stop_times`, but that is the *timetable*: it says where a bus was meant to be,
and the whole product is the difference between that and where it was.

So `arrivals.py` makes the weakest claim that is still useful: **a vehicle is
at a stop while it is within fifty metres of it, and one unbroken run of
readings inside that circle is one visit.** It needs no stop-to-line relation
— this model has none, and GTFS's own is a property of a trip rather than a
line — and it finds a bus serving a stop it was never scheduled for, which is a
thing operators do and timetables do not record. Fifty metres is the figure
GTFS-RT consumers settle on and it is a compromise both ways: tighter and a
reading taken across a wide forecourt misses, looser and two stops either side
of a junction become one.

It runs nightly, **before** the sweep that drops the partition it reads —
a visit inferred from rows already in R2 is a visit nobody infers.

`headway_s` is the number worth the whole table. A ten minute timetable run as
a pair four minutes apart and then a sixteen minute hole is on time by every
average in `serviceHour` and unusable to the person standing at the stop.
Bunching is invisible everywhere else in this module.

**What it will not do is count boardings.** Occupancy is a percentage of
capacity with a counter's error either side of it, and the difference between
two of them is that error twice over. A boarding figure derived that way is a
guess, and a guess drawn as a fact is the one thing that makes an operator stop
trusting the screen.

---

## 3c. One vocabulary for narrowing a screen

The map and Insights ask the same question — *only this line, only this
vehicle, only the metro* — of different tables. Before `facets.py` they each
carried their own answer: `live.at` took a `line` string and `insights.rhythm`
took a different one, and nothing took a vehicle at all. Two implementations of
one idea is how a filter comes to mean something slightly different on two
screens of one product, and nobody notices until somebody compares them.

A facet is one of two things. **Direct** — the fact table has the column, so
narrowing is a `WHERE`. **Through** — the table has no such column and never
should: a mode is a property of a *line*, not of a position, and denormalising
"Metro" onto forty million rows to save a lookup is the wrong trade by four
orders of magnitude. So `mode=Metro` resolves against the doctype first and
arrives as the set of lines it names.

Two facets landing on the same column intersect rather than replace: a mode and
an agency chosen together mean the lines that are both.

It resolves on the server because resolution reads doctypes — so it runs as the
person asking, cannot widen what they may see, and a facet never offers a line
their User Permissions hide. A browser that resolved its own facets would be a
browser deciding which lines exist.

**A facet a table cannot answer is refused, not ignored,** and refused before
it is used rather than after. `serviceHour` has no vehicle column, so the
Insights network tab reports `vehicle` as unavailable whether or not anybody has
chosen one, and the control greys itself out. Reporting it on use would mean a
control that looks available right up to the moment it silently does nothing.

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

## 7a. Reading the history forward, without a model

None of what follows is machine learning, and none of it should become machine
learning. Every number here is arithmetic over data we already hold — a
percentile, a gradient, a projection along a line — which makes each one
explainable to a customer, cheap to compute, correct on a workspace with no
credits, and impossible to get subtly and unaccountably wrong. That is not a
limitation accepted reluctantly; for these questions it is simply the better
engineering.

The point that reorganises the analytical half: **prediction is not a
subsystem, it is a second reader of the aggregate tier**. The roll-up in §3a
already computes, per line, per stop, per hour, per weekday, what actually
happened. That table *is* the model for almost everything worth predicting, and
the interesting work is not building a predictor — it is storing the right
numbers in the first place.

Which means one concrete change to that tier: **store percentiles, not means.**
A mean travel time answers no question anybody has. The 85th percentile is what
a scheduler builds a timetable from, the 50th is what an ETA should say, and
the spread between them is the uncertainty a forecast has to show. Keeping
p50/p85/p95 alongside the count costs three columns and is the difference
between a chart and a product.

### What is genuinely predictable, in the order it works

1. **Arrival time.** A vehicle is at a known point with a known delay; when
   does it reach the next six stops? The honest first version is not a model —
   it is a lookup of the historical distribution for that segment at that hour
   on that weekday, offset by the current delay. A percentile table beats most
   fitted models here, and it is explainable to somebody who does not trust
   software.
2. **Punctuality risk.** The same distribution, stated as a probability rather
   than a point: "this trip reaches the terminus more than five minutes late on
   seven runs in ten at this hour". An operator acts on risk, not on a number.
3. **Bunching.** On a frequent line, vehicles catch each other, and the gap
   collapses predictably. Detecting it live is arithmetic on two positions;
   predicting it is extrapolating one gap. No model at all, and it is the thing
   an operator can actually intervene on — which makes it the highest ratio of
   value to effort in this list.
4. **Occupancy and demand.** Strongly periodic: hour, weekday, school term,
   weather, events. Classic seasonal decomposition, and it works.
5. **Anomaly.** "This trip is behaving unlike its own history" is a z-score
   against the same table. It catches incidents without anybody having to
   define what an incident is, which is the only way that feature ever works.
6. **Dwell time** as a function of boardings, which is what makes 1 accurate
   rather than merely present.

What is **not** on this list: what-if simulation — "add a bus at 07:00 and what
happens to load" — which is a different discipline, needs a network model
rather than a history, and should be refused rather than approximated.

### Moving the vehicle between pings

Everything above is about minutes and hours. This is about the next second, and
it is what makes the map look like software somebody paid for.

A feed reports every 15 to 30 seconds. A marker that jumps every 20 seconds
reads as broken, so between reports the vehicle is **moved by dead reckoning
along the route shape** — projected forward at its recent speed, following the
polyline rather than a straight line, because a bus follows the road and a
straight line puts it through a building. That is one geometric step per frame,
in the browser, over data already loaded.

Four details are the whole difference between convincing and amateurish:

* **Map-match the reported position.** Raw GPS lands in gardens and on roofs.
  Project it onto the line's own shape, which is a point-to-polyline
  projection, and the vehicle sits on its route because that is where it is.
* **Never snap.** When the true position arrives, ease to it over about a
  second rather than teleporting. A marker that jumps looks wrong even when it
  has just become more correct.
* **Speed from the recent past, not from one gap.** Two consecutive reports
  give a noisy speed; a short rolling window gives one that does not oscillate.
  Near a stop, expect a stop: the shape knows where the stop is and the
  historical dwell time says how long it sits there.
* **A silent vehicle is drawn differently.** When reports stop, carry it
  forward on the timetable and its last known delay for a short grace period,
  drawn faintly, then stop and say the position is stale. A stale position
  drawn as though it were live is the one thing that makes an operator stop
  trusting the screen.

The same projection answers "where is it now" for a vehicle that has never
reported at all: on its shape, at the point the timetable says, which is a
better answer than an empty map and is honestly labelled as scheduled rather
than observed.

### Demand, per stop and per hour

"How busy is this stop on a Saturday afternoon" is not a forecast at all for
any period we have already seen — it is a `GROUP BY` over `stopHour`, and it is
instant. Note the wording: *busy*, not *boarding*. We measure visits, dwell,
headway and how full the vehicle was when it pulled in; we do not measure how
many people got on, and §3b says why we will not derive it. It only becomes a prediction for a date in the future,
and then it is the same table read against the calendar: this stop, this hour,
this weekday, school term or not.

Which is worth saying plainly because it sets the order of work: **the
historical version of every demand question is free once the roll-up exists,
and it is most of the value.** The forward-looking version is a second read of
the same numbers, and nothing in between needs building.

### The scrubber earns a second use

The time control in §4 has a right-hand side. Past on the left, forecast on the
right, one control, with the uncertainty band widening as it goes forward and
the vehicles on the map becoming ghosts. That is the demo: the same gesture
that shows what happened shows what is about to.

It is also an honest design, because it makes the uncertainty visible rather
than hiding it behind a single number. **A forecast is never drawn without its
spread.** A confident wrong ETA costs more trust than no ETA.

### We have to score ourselves

Every prediction is written down with what it predicted and when, and a job
scores it against what happened. Without that we cannot answer "is it any
good", cannot tell a customer, and cannot notice the day it stops working
because a line was rerouted.

It also decides the cold start honestly: a workspace with no history has no
distribution, so an ETA is the timetable plus the current delay and the screen
says so. Software that pretends to know is worse than software that says it is
still learning.

### Where AI earns its cost, and where it is theatre

Points 1–6 are statistics. Putting a language model on them would be slower,
dearer and worse, and we meter every AI call, so it would also be visibly
worse. The gateway is not the tool for arithmetic.

Where it earns its place is **the sentence**, and this product's buyer is
exactly the person who wants one: turning "line 12, p85 delay 8.4 min, 14 of 21
weekday mornings, segment Hbf→Markt" into *"Line 12 is reliably late leaving
the Hauptbahnhof on weekday mornings, and it has been since March."* And the
other direction — a question typed in German becoming an aggregate query.

Both operate on the rolled-up numbers, never on raw observations, which keeps
them cheap and keeps them compatible with a customer who has AI switched off
entirely.

## 7b. Layers over the map, and why none of them is a heatmap

`geo.py` answers *where*. Insights answers *when* — an hour, a weekday, a line
— and the two are not interchangeable. A line that averages four minutes late
is a fact about a line; that it loses all four of them on one bridge between
two particular stops is a fact about a **place**, and it is the one an operator
can act on. No chart in this product can hold it, because a chart has no
geography.

**MapLibre ships a `heatmap` layer and it is the wrong tool here.** It renders
kernel *density*, so a cell with two hundred readings averaging thirty seconds
late glows brighter than one with ten readings averaging ten minutes late.
Weighting by delay does not fix it — density still dominates the kernel. What
answers "where is it late" is the **mean per place**, so the rows are grouped
into a grid and each cell carries its own average. Density becomes the
**opacity**, which is where it belongs: a cell nobody has driven through often
is drawn faintly, because it is a weaker claim rather than a cooler one. Below
eight readings a cell is dropped rather than faded — the honest thing to say
about one bus that once went through is nothing.

A cell is a rounded latitude and longitude, and how rounded follows the zoom:
kilometre cells for the shape of a city, hundred-metre for a district,
ten-metre once a street fills the screen. Three buckets rather than a
continuous function, so panning about at one zoom does not re-ask the server
for an answer it already has. The first version binned at a fixed hundred
metres and drew the whole surface at city zoom, where a cell is two pixels
under an eight-pixel route line — it looked, convincingly, like nothing had
happened.

The colour range is the 5th and 95th percentile, not the min and the max. One
cell where a bus sat broken down for an hour is a real reading and a terrible
top of scale: it flattens every other cell into the first step of the ramp.

There are five layers and they come in two shapes, declared once in
`frontend/src/modules/onemobility/lib/layers.js` — which the map, the switcher
and the key all read, because three places that have to agree about what a
layer is called and what its colours mean is exactly enough for them to stop
agreeing:

* **surface** — a measure averaged into a grid, read off `observation` and
  drawn as tiles *under* the routes, because it is the ground the network runs
  over. *Where it runs late* (diverging, because lateness has a real zero) and
  *where it fills up* (the same five colours the vehicles wear, so a reader who
  has learnt that orange means standing does not learn a second scale).
* **points** — a measure per stop, read off `stopHour` and drawn as graduated
  circles *over* the routes, because it happens **at** something. *Where the
  service goes* (visits) and *where the wait bunches* (the p85 headway over the
  average). Area tracks the value rather than radius: a circle twice as wide
  reads as four times as much.

One overlay at a time, and not a stack of checkboxes — two of these are tiled
surfaces and two are graduated circles, and any two at once is mud. The three
base layers below it (routes, stops, vehicles) are independent because they are
different *things* rather than competing answers to one question.

The surface reads `observation` rather than any rolled tier, because none of
them keeps a position: the roll-ups are per line, per vehicle and per stop, and
a place is none of those. That bounds it to the hot window, which the screen
says rather than hides. It is narrowed by the same facet bar as everything
else, and the chosen layer lives in the URL — "the corridor where U6 loses its
time" should be a link somebody can send, not a screenshot.

---

## 7c. What a person can do to the map

Four things, and each of them is here because a map that only shows is half a
map.

**The controls are a rail, the legend is a key.** They were one card, and it had
become a control panel with a scrollbar in which the thing a reader actually
wanted — what does this orange mean — was below the fold. So the controls are
icon buttons under the zoom, where every web map worth using puts them, and the
legend went back to being a legend: read-only, bottom-left, and every row in it
present only while the thing it explains is drawn. An empty map with a key
explaining four scales is how people learn to stop reading the key.

**One line, looked at alone.** Click a route and it stays in its colour while
everything else goes grey at a third opacity; click it again, or click the
ground, and the network comes back. Monochrome rather than hidden, and that is
the design rather than a shortcut: a route drawn alone on a blank ground has
lost which junctions it crosses and which corridor it shares, and those are
usually what somebody isolating it is trying to see.

This is deliberately **not** a facet. A facet is a question put to the server —
how did U6 run — and re-asks every query on the screen; isolation is a way of
looking, costs nothing and never re-fetches. The first version conflated them,
and picking one vehicle out of a crowd re-queried a month of history.

**A marker faces the way the road goes.** The bearing comes from the tangent of
the line's own shape at the point the vehicle has reached, not from where the
marker moved between two frames. Frame-to-frame is wrong twice: a vehicle
standing at a stop has no movement to take a bearing from, so it keeps whatever
it had and a newly-appeared one points north; and a marker eased onto a
corrected position swings to face the correction rather than the road. The
shape is run in both directions, so the tangent is turned through 180° for a
vehicle whose projected position is going backwards along it — otherwise half
the fleet drives backwards up its own route. `motion.tangent` is pure and
unit-tested; `motion.advance` returns the point and the bearing off one pair of
projections, because asking for each separately is the same O(n) walk twice,
per vehicle, per frame, sixty times a second.

**Hovering says what the thing is.** A stop gives its name and how many lines
have been seen there; a vehicle gives its fleet number, its line, how full it is
and how late; a route gives its number, its name and how many of it are out
right now. Built as HTML strings rather than components, because MapLibre's
popup takes markup and mounting a component per hover would be a mount and an
unmount on every pixel of a drag. Everything that reaches one goes through
`escapeHtml`: a stop is named by a customer's feed, and a feed is not a trusted
author.

---

## 7d. A mode is not a shape

`markers.py` and `Transit Marker Style` exist because those are two different
things and conflating them is the mistake. A **mode** is what a network runs: it
comes off the feed, Insights groups by it, and renaming it to change a picture
would corrupt every number. A **shape** is what the map draws. They start
identical — so a workspace that never opens the picker sees exactly what it saw
before any of this existed — and they come apart the first time a customer whose
"Rail" is really a light rail wants the tram outline across their whole S-Bahn.

Two levels: `Transit Marker Style` holds one row per mode, and
`Transit Line.marker_shape` overrides it for one line — a heritage tram on a bus
network, a rail replacement that is really a coach. Empty follows the mode,
which is what nearly every line is.

A doctype rather than a saved view, because it is a **workspace's** decision and
not a reader's: a control room where two screens draw the same tram differently
is a control room having an argument about which screen is right. It gets
permissions, a history and an audit trail like every other document, and no
screen of its own — the picker is on the map, because what is being chosen is a
picture and a picture is chosen by looking at where it lands.

Resolved on the server and sent already resolved, so the browser never carries
the mapping table: `shape()` hands it a line that already knows what it looks
like. `tests/test_marker_shapes.py` holds the three lists that must agree and
cannot see each other — the outlines `markers.js` can draw, the shapes the
server will accept, and the options the doctype offers. A Select option with no
drawing behind it is a promise the map keeps by silently drawing a capsule for
ever.

---

## 8. What the engine was missing, and what it now has

Three of the five gaps below were OneSpace's rather than OneMobility's, and
were built there so the next space inherits them. That was the whole point of
writing this section before writing the space.

**Built, in the engine:**

* **A map view type**, over `Geolocation` or over a pair of coordinate fields —
  `spaceview/views.py` resolves which, `MapBody.vue` draws it, and a screen
  opts in by naming `map` in its `view_types`. Any doctype with a position gets
  a map; stops are only its first customer.
* **The ground under it.** `onespace/basemap.py` and `lib/screen/basemap.js`
  are the one place the product decides where tiles come from — site config, on
  the boot payload, because which tile store a bench points at is a deployment
  fact. Raster by default so a style that cannot be fetched cannot take the
  whole map with it, and a flat ground when there are no tiles at all, which is
  what a schematic looks like and is what makes this work offline.
* **Tiered storage, declared rather than written.** `shared/facts.py`: a module
  says "this is a fact table, keep 30 days hot, roll it up like *this*, freeze
  the rest" and the engine does the partitioning, the nightly roll-up, the
  freeze to R2 and the hydrate on request. Percentiles included, because p85 is
  the number a scheduler builds a timetable from and SQL cannot compute one in
  a grouped pass. Swept nightly from `hooks.py`; nothing in the module knows
  which tier a row is in.
* **A space that acts when it is enabled or removed.** `onespace/spacelife.py`:
  a space may ship a `lifecycle.py`, and enabling, disabling or removing it
  calls one. Fact tables have to be created before the space works and are
  nobody's to clean up otherwise.

**Still missing, in the order it now blocks:**

1. **A screen body over an aggregate API.** Insights is a `component` screen
   reading `onemobility/insights.py`, which works and is honest — but the next
   space with a fact table will write the same screen again. A `dashboard` view
   whose widgets can name an aggregate rather than a doctype is the general
   form.
2. **Time-series charts that survive a hundred thousand points** — decimation
   in the query, not in the browser. The aggregate tier hides this for now
   because it is already grouped.
3. **A settings tab a space can contribute.** Sources are a list screen with a
   "Fetch now" action, which is enough; they are settings-shaped and would sit
   better in the workspace's own dialog, and a space cannot put a tab there.

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
* **No subprocessor sees the data**: AI off unless enabled, and nothing about a
  workspace's records leaves it. The one exception is the map's background,
  which the *reader's browser* fetches from a tile host — so that host sees an
  address and a tile number, and never a route, a vehicle or a search. It is
  named in the subprocessor list, it is one config key to point at a tile store
  we run, and `oneapp_map_plain` turns it off entirely: the map then draws its
  ground flat and every record still on it. For the customer who asks, that is
  a real answer rather than a reassurance.
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

Each ships something a person can look at. **Done** is done and in the fixture.

1. **The model and one importer.** Doctypes for the reference nouns, the fact
   tables, and GTFS static from an upload — GTFS before VDV because the sample
   data is abundant and it proves the model is not VDV-shaped. **Done.**
2. **The map view type**, in the engine, over Geolocation. Stops on a map, and
   every other space gets it too. **Done**, with the basemap under it.
3. **VDV 452 over SFTP.** The real acquisition path, on the pipeline stage 1
   proved. **Half done:** the SFTP door is built and takes the newest file in a
   drop folder; the VDV 452 normaliser is not written, and a source declaring
   that format is told so plainly rather than failing as a parse error.
4. **The network screen, static.** Lines drawn from shapes, coloured, filtered,
   with a legend. **Done.**
5. **Live.** A socket source, the observation table, vehicles moving. **Done**
   except the socket itself: `live.report` is the door, and nothing holds a
   long-lived connection open yet.
6. **The scrubber.** The nightly roll-up, the day objects, and one screen with
   two clocks. **Done.**
7. **Analysis.** Peak hours, punctuality, occupancy over time — the aggregate
   API and the charts on it. **Done:** the Insights screen.
8. **Sources, plural.** Precedence, conflicts, inferred stops, the connection
   surface. **Half done:** precedence is a field and inferred stops are drawn
   differently; nothing resolves a conflict between two sources yet.
9. **Forecast.** The percentile roll-up read forwards — ETAs, punctuality risk,
   bunching — the scrubber's right-hand side, and the scoring job that says
   whether any of it is any good. **Started:** `bunching` is built and
   `facts.aggregate` computes percentiles; ETAs and the scoring job are not.

Stages 1–4 are a sellable demo. Stages 5–6 are the product. Stages 7–9 are what
renews it, and stage 9 is what makes a competitor's version look like a
screenshot.

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

What `scripts/dev.sh seed` builds today is six Berlin lines across four modes
(the 100 bus, U1, U2, U6 and U8, and the S1), each with its operator's own
colour and its real coordinates, sharing interchange stops the way the network
does — so a map with every line drawn has crossings in it, which is the only
way to tell whether the casings work. Ten vehicles report every sixty seconds
over a fourteen-hour service day.

Two of those numbers are load-bearing and were not obvious. Six lines rather
than three, because a categorical palette that reads cleanly at three tells you
nothing about the pair a reader actually has to separate. And lateness is
per-line and shaped by the hour — `_lateness()` gives each line its own
multiplier over a peak-hour base, plus a deterministic spread — because the
first fixture had every line identically punctual, which drew four charts that
were flat and one that was a single bar at a hundred percent. A fixture that
makes every plot look correct is worse than no fixture: it hides exactly the
bugs the plots exist to show.

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
