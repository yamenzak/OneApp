"""What OneMobility adds to the agreements.

The clauses that matter say the thing a transport authority's lawyer will look
for: that we hold vehicle telemetry rather than passenger data, and what
becomes of an individual position once it has aged.

Nothing here says anything about the map's tiles. The map is the engine's, not
this space's — every space can draw one — so where its background comes from is
declared in `onespace/legal.py` beside the rest of the platform's suppliers.
"""

from ..onelegal.registry import clause

M = "OneMobility"

clause(
    document="privacy", section="modules", key="mobility-telemetry", module=M,
    body="""
        OneMobility holds timetables, vehicle positions, occupancy counts and
        punctuality. None of it identifies a passenger: an occupancy figure is
        a count of people on a vehicle and not a record of who they were, and we
        neither ask for nor accept a feed that names one.
    """,
)

clause(
    document="privacy", section="modules", key="mobility-retention", module=M,
    body="""
        Individual vehicle positions are kept for a period you choose in the
        workspace's settings, and are then deleted. What survives is the
        aggregate — how full a line runs at a given hour on a given weekday —
        which is a statistic and not a movement.
    """, order=20,
)

clause(
    document="terms", section="modules", key="mobility-sources", module=M,
    body="""
        You may connect timetable and telemetry sources of your own, by upload,
        SFTP, HTTP or a live socket. You confirm that you are entitled to
        supply that data to us. Where two sources disagree, OneMobility shows
        the one your own precedence prefers and keeps the other; it does not
        discard either.
    """,
)

clause(
    document="terms", section="modules", key="mobility-estimates", module=M,
    body="""
        Arrival times, punctuality risk and demand figures are estimates
        computed from your own history. They are shown with the spread around
        them and are not a guarantee of service. OneMobility does not control
        vehicles and is not an operational safety system.
    """, order=20,
)
