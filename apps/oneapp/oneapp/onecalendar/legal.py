"""What OneCalendar adds to the agreements."""

from ..onelegal.registry import clause

M = "OneCalendar"

clause(
    document="privacy", section="modules", key="calendar-what", module=M,
    body="""
        OneCalendar holds the events you create — their titles, times,
        descriptions and the people invited to them — and reads the dates
        already on the records in your workspace. It does not connect to an
        outside calendar and nothing leaves the workspace.
    """,
)
