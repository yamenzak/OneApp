"""OneCalendar — everything with a date on it, merged for the person asking.

One module and, for now, one file. It is a *merge* first: most of what a
calendar shows belongs to some other module and says where it came from, so
this reads every screen the person may open that declares a calendar, through
the same path that screen's own calendar uses. It is a small store second, over
Frappe's own `Event`, which is where a workspace already keeps the things that
are nobody's record but somebody's Tuesday.

That is also why there is no doctype here.
"""

from .diary import agenda, event, remove_event, save_event

__all__ = ["agenda", "event", "remove_event", "save_event"]
