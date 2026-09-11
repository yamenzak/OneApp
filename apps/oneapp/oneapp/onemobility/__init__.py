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
    vdv452      a German planning delivery read into the same one
    vdv457      the counting-data interface: how many got on, measured at the
                door, which is the one number nothing else here may state
    sniff       what a delivery actually is, decided from its bytes rather
                than from a dropdown or an extension — and what had to be
                forgiven to say so
    sources     the four doors a delivery arrives through, and the one pipeline
    conflicts   two sources claiming one key: whose answer is drawn, and where
                the other one went
    streaming   the door that never closes — a socket read in bounded windows,
                in SIRI, VDV 454, VDV 457 or GTFS-Realtime
    gtfsrt      protocol buffers, decoded off the wire format rather than off a
                dependency
    timetable   what the feed plans, kept as a pattern: a departure board, the
                ghosts on the forward scrubber, and the plan against what ran
    live        positions in, positions out, one vehicle's day for the scrubber
    arrivals    positions turned into stop visits, which is how a stop gets a number
    facets      one vocabulary for narrowing every screen: line, vehicle, stop, mode
    forecast    the same aggregate tier read forward — an arrival, a risk, an
                anomaly, and never a number without the spread it rests on
    scoring     what the forecast claimed, written down before the answer
                existed, and checked against it the night after
    geo         the map's analytical layers — what the network does *somewhere*
    network     the drawn network, and the numbers read off the aggregate tier
    insights    the aggregate tiers as plots — the network, the fleet, the stops
    legal       what this module adds to the agreements
    lifecycle   what enabling and disabling it does to the data
    markers     which silhouette the map draws for a line, and who decides
"""

from .conflicts import accept_stop, disagreements
from .facets import offered
from .forecast import bunching_risk, expect, outlook, risk, unusual
from .geo import demand, surface
from .gtfs import load_feed
from .insights import fleet, rhythm, stops
from .live import at, report, thaw, track
from .lifecycle import forget_everything
from .scoring import accuracy
from .markers import marker_styles, set_marker_style
from .network import bunching, days, punctuality, shape
from .sources import fetch_now
from .timetable import deviation, due, expected
from .streaming import listen_now

__all__ = [
    "accept_stop",
    "accuracy",
    "at",
    "bunching",
    "bunching_risk",
    "days",
    "demand",
    "deviation",
    "disagreements",
    "due",
    "expect",
    "expected",
    "fetch_now",
    "fleet",
    "forget_everything",
    "listen_now",
    "thaw",
    "load_feed",
    "marker_styles",
    "offered",
    "outlook",
    "punctuality",
    "report",
    "rhythm",
    "risk",
    "set_marker_style",
    "shape",
    "stops",
    "surface",
    "track",
    "unusual",
]
