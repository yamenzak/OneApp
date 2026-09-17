# Flows

## Three doors, one pipeline — `sources.py`

A source is a folder, an endpoint or an upload. `fetch_now` and `load_feed` are
the two entry points and both land in the same place: a `Transit Feed` row, the
file in the Drive, and the parse.

`sniff.py` decides what arrived. `gtfs.py` and `gtfsrt.py` read the two open
standards; `vdv.py` and the three `vdv*` modules read the German ones —
`docs/` calls that the VDV shelf, and `README.md` §5a has the column nobody
else writes down.

## Duplicates are a conflict, not magic — `conflicts.py`

Two sources describing the same stop is the normal case, not an error. Each
source has a `precedence`; a `Transit Claim` records what each one *said*, and
`verdict` says which won.

`disagreements()` lists what is contested and `accept_stop` is a person
deciding. **Nothing merges silently**, because a stop that quietly changed its
coordinates is a map that is wrong in a way nobody can find.

## Nobody may edit what a source said

`Transit Claim` is Read for every seat. The answer to "this is wrong" is to
change the precedence or fix the feed — an editable audit trail is not one.

## Playback is an object, not a query — `live.py`

`at(when)` answers where everything was. For a past day, the browser fetches
the day's **track objects from R2** and scrubs: they are already the playback
format, so there is no rehydration and no query.

`live.at` says **`frozen`** when the day asked for is past the window and
sitting in the bucket — an empty frame has two meanings and only the server can
tell them apart. The Network screen then offers "Bring this day back", which
enqueues `thaw`: **every raw tier for that day**, not just positions, because
half a day is worse than none. The day is held for a week so that night's sweep
does not undo it.

`track`, `relay` and `report` are the live ends.

## Where a vehicle is between two pings — `frontend lib/motion`

Interpolation is the browser's, not the server's. The server sends what was
observed; the map draws what that implies.

## Reading the history forward — `forecast.py`

**Not a model, and not a second subsystem — a second reader of the aggregate
tier.** `outlook`, `expect`, `risk`, `bunching_risk`, `unusual`, `faults`.

This is why the aggregate tier stores percentiles: "seven times in ten this
stop is more than four minutes late" is a percentile, and no mean produces it.

## Measuring — `network.py`, `insights.py`, `scoring.py`

`punctuality`, `bunching`, `days`, `shape`; `rhythm`, `fleet`, `stops`;
`accuracy`. Every one of them reads the aggregate tier and returns rows already
grouped.

**The read path is an aggregate API and never a query builder.** Screens ask
"occupancy by hour for line 12 in March"; they never ask for rows. The day a
customer's volume outgrows MariaDB the endpoint is reimplemented and no screen
changes — writing screens against raw rows is what would make that swap a
rewrite.

## The map — `geo.py`, `markers.py`, `basemap` (the engine's)

`surface` and `demand` are the layers, and **none of them is a heatmap** —
README §7b is why. `marker_styles` and `set_marker_style` are how a mode gets a
shape, and §7d is why a mode is not a shape.

## Forgetting — `lifecycle.py`

`forget_everything` is the operator-facing end of §9: a customer who wants
their history gone gets it gone, including the frozen copies.
