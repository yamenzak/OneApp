"""OneMobility — public transport data, read.

`README.md` beside this file is the argument: what the model is, why the facts
are not documents, why playback is an object rather than a query, and what to
offer an operator who thinks their load factors are a trade secret.

The shape, in one paragraph. A **source** delivers a **feed**; a feed is read
into the reference nouns (`Transit Agency`, `Line`, `Stop`, `Vehicle` — real
doctypes, because a person opens them) and the fact tables (`observation`,
`trip`, `serviceHour` — not doctypes, because two million rows a day cannot be).
The **network** screen draws the lines and stops; **live** answers "where was
everything at time T" for one clock that is either now or a Tuesday in March.

    model       the fact tables, declared against shared/facts.py
    gtfs        a GTFS zip read into that model
    live        positions in, positions out, one vehicle's day for the scrubber
    network     the drawn network, and the numbers read off the aggregate tier
    legal       what this module adds to the agreements
    lifecycle   what enabling and disabling it does to the data
"""

from .gtfs import load_feed
from .live import at, report, track
from .lifecycle import forget_everything
from .network import bunching, days, punctuality, shape

__all__ = [
    "at",
    "bunching",
    "days",
    "forget_everything",
    "load_feed",
    "punctuality",
    "report",
    "shape",
    "track",
]
