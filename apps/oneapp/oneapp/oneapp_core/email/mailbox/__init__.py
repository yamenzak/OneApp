"""Reading and writing one person's mail.

Mail in this product is already a document — inbound writes a `Communication`,
Frappe's IMAP sync writes a `Communication`, replying writes one — so there is
no mail store here, only a list to scope and an ordering to get right.

The layers, in import order. A module may use the ones above it, never below:

    scope       whose mail this is, and which folders it has
    flags       read and starred, per person
    query       a folder and a search term, as a query
    reading     the rail, the conversations, one conversation
    filing      moving a conversation
    sending     sending, and unsending
    drafts      what somebody typed and did not send
    composing   the composer, already filled in

The one rule worth carrying between them: `_filters` returns both halves of its
filter together, because a caller that took one half would be asking for every
`Communication` on the site.
"""

# Shared so a test can stub it in the one place every layer sees: a name
# imported into a module is a copy, but a module is the same object everywhere.
import frappe

from oneapp.oneapp_core.email import folders as folder_ops, people
from oneapp.oneapp_core.email.folders import FOLDER_FIELD, QUIET
from oneapp.oneapp_core.email.threading import THREAD_FIELD

from .scope import (
	ICONS,
	PAGE,
	PREFIX,
	SENT,
	SPLIT,
	_account_of,
	_accounts,
	_addresses,
	_held,
	_like,
	normalise,
	strip_prefixes,
)
from .flags import SEEN_KEY, SEEN_LIMIT, STARRED_KEY, _seen_set, _starred_set
from .query import SEARCH_CEILING, _filters, _in_thread, _matching, _preview
from .reading import folders, mark_read, mark_unread, star, thread, threads, unread
from .filing import _into, add_folder, archive, bin, drop_folder, file_thread
from .sending import UNDO_SECONDS, _carry, _names, send, unsend
from .drafts import DRAFT_KEY, forget, keep, kept
from .composing import _quote, draft

__all__ = [
	"DRAFT_KEY",
	"ICONS",
	"PAGE",
	"PREFIX",
	"SEARCH_CEILING",
	"SEEN_KEY",
	"SEEN_LIMIT",
	"SENT",
	"SPLIT",
	"STARRED_KEY",
	"UNDO_SECONDS",
	"_account_of",
	"_accounts",
	"_addresses",
	"_carry",
	"_filters",
	"_held",
	"_in_thread",
	"_into",
	"_like",
	"_matching",
	"_names",
	"_preview",
	"_quote",
	"_seen_set",
	"_starred_set",
	"add_folder",
	"archive",
	"bin",
	"draft",
	"drop_folder",
	"file_thread",
	"folders",
	"forget",
	"keep",
	"kept",
	"mark_read",
	"mark_unread",
	"normalise",
	"send",
	"star",
	"strip_prefixes",
	"thread",
	"threads",
	"unread",
	"unsend",
]
