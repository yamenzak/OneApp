"""The icons an app in the registry may use.

frappe-ui renders `lucide-*` names as Tailwind utility classes, and Tailwind's
JIT only emits CSS for classes it can find as *literal strings* in the source.
An operator-typed icon name is not in any source file, so it emits nothing and
the launcher renders an empty box — the icons page says so outright, and gives
the two ways out: a known set written as literals, or `~icons/lucide/*` imports
for a genuinely open one.

A registry of apps we define is a known set, so this is that list. It is written
into the SPA as literals (which is what makes the CSS exist) and into the
doctype as Select options (which is what stops a name outside it being saved).
Both are generated from here, so they cannot drift.
"""

# Grouped by what an app is, not by glyph, so the list stays choosable — and
# the grouping is data rather than a comment now, because the picker draws it.
#
# The words beside each icon are what a person types to find it. They were
# already written here as comments; a comment is not searchable, so they moved
# into the tuple. Nobody looking for the sales app types "chart line".
SPACE_ICON_GROUPS = [
    ("General", [
        ("lucide-layout-grid", ("grid", "launcher", "apps", "default", "home")),
        ("lucide-database", ("data", "records", "storage", "table")),
        ("lucide-sparkles", ("ai", "automation", "magic", "assistant")),
        ("lucide-shield", ("compliance", "security", "policy", "audit")),
    ]),
    ("People", [
        ("lucide-users", ("crm", "contacts", "customers", "people", "team")),
        ("lucide-user-round", ("hr", "people", "staff", "employee", "person")),
        ("lucide-graduation-cap", ("training", "lms", "learning", "course")),
        ("lucide-stethoscope", ("healthcare", "medical", "clinic", "patient")),
    ]),
    ("Work", [
        ("lucide-briefcase", ("projects", "work", "tasks", "jobs")),
        ("lucide-calendar", ("scheduling", "calendar", "events", "bookings")),
        ("lucide-clock", ("timesheets", "attendance", "hours", "time")),
        ("lucide-wrench", ("maintenance", "service", "repairs", "field")),
    ]),
    ("Money", [
        ("lucide-file-text", ("documents", "invoices", "quotes", "papers")),
        ("lucide-receipt", ("billing", "expenses", "receipts", "claims")),
        ("lucide-wallet", ("finance", "payments", "accounts", "money")),
        ("lucide-shopping-cart", ("commerce", "orders", "sales", "shop")),
    ]),
    ("Goods", [
        ("lucide-package", ("inventory", "stock", "items", "warehouse")),
        ("lucide-truck", ("logistics", "delivery", "shipping", "fleet")),
        ("lucide-factory", ("manufacturing", "production", "plant", "works")),
        ("lucide-store", ("retail", "pos", "shop", "branch", "outlet")),
    ]),
    ("Talking", [
        ("lucide-message-square", ("chat", "support", "helpdesk", "tickets")),
        ("lucide-mail", ("email", "campaigns", "newsletter", "inbox")),
        ("lucide-phone", ("telephony", "calls", "phone", "dialer")),
    ]),
    ("Numbers", [
        ("lucide-chart-line", ("analytics", "reports", "trends", "metrics")),
        ("lucide-chart-pie", ("dashboards", "insights", "breakdown", "share")),
        ("lucide-book-open", ("knowledge", "docs", "wiki", "handbook", "notes")),
    ]),
]

# The flat list, in group order. Written out as literals in the SPA, which is
# what makes the CSS exist, and written into the doctype as Select options,
# which is what stops a name outside it being saved.
SPACE_ICONS = [icon for _group, icons in SPACE_ICON_GROUPS for icon, _words in icons]

# What each icon answers to, for the picker's search box.
SPACE_ICON_WORDS = {
    icon: words for _group, icons in SPACE_ICON_GROUPS for icon, words in icons
}

DEFAULT_SPACE_ICON = "lucide-layout-grid"


# --------------------------------------------------------------------------- #
# Status glyphs
#
# A second closed set, and closed for the same reason the first one is: Tailwind
# emits CSS only for class names it finds as literals, so an icon that exists
# only in a database draws an empty box.
#
# Separate from SPACE_ICONS because these answer a different question. Those say
# what an app *is* — a truck, a wallet, a stethoscope. These say where a record
# *stands*, and the vocabulary is small because the answers are: it is fine, it
# is working, it is waiting, it went wrong, it is finished, it is gone.
# --------------------------------------------------------------------------- #
STATE_ICONS = [
    "lucide-circle-check",     # settled, fine, active
    "lucide-circle-dashed",    # draft, not started
    "lucide-circle-dot",       # open, in hand
    "lucide-loader",           # running, provisioning
    "lucide-clock",            # waiting on somebody else
    "lucide-triangle-alert",   # needs attention
    "lucide-circle-x",         # failed, refused
    "lucide-circle-pause",     # suspended, held
    "lucide-archive",          # archived, retired
    "lucide-trash-2",          # purged, deleted
    "lucide-arrow-down-left",  # money in
    "lucide-arrow-up-right",   # money out
    "lucide-tag",              # a category rather than a state
]

# Which glyph a state's own words earn, in order — first match wins.
#
# Derived rather than declared, because the alternative is typing an icon name
# beside all 52 Select options and the words already say it. `Failed` and
# `Broken` mean the same thing to a reader and should not need two decisions.
# A doctype that disagrees declares its own; see `gen_doctypes.states=`.
STATE_ICON_WORDS = [
    ("lucide-circle-x", ("failed", "broken", "cancelled", "canceled", "refused",
                         "rejected", "lost", "abandoned")),
    ("lucide-trash-2", ("purged", "deleted", "destroyed")),
    ("lucide-archive", ("archived", "retired", "withdrawn", "expired", "closed",
                        "deprecated", "released", "ignored")),
    ("lucide-circle-pause", ("suspended", "paused", "held", "on hold", "draining",
                             "maintenance", "past due", "overdue", "blocked")),
    ("lucide-triangle-alert", ("warned", "review", "over", "full", "attention",
                               "incomplete", "unpaid")),
    ("lucide-loader", ("provisioning", "running", "creating", "bootstrapping",
                       "restoring", "syncing", "processing", "pending")),
    ("lucide-clock", ("requested", "awaiting", "queued", "scheduled", "trialing",
                      "trial", "received", "preview")),
    ("lucide-circle-check", ("active", "succeeded", "success", "completed",
                             "complete", "done", "paid", "ready", "available",
                             "processed", "committed", "claimed", "resumed",
                             "cleared", "taken", "restored", "granted")),
    ("lucide-circle-dot", ("open", "draft", "new")),
    ("lucide-arrow-down-left", ("grant", "purchase", "refund", "credit")),
    ("lucide-arrow-up-right", ("spend", "charge", "debit")),
]


def state_icon(title: str) -> str:
    """The glyph a state's words earn, or the neutral tag.

    A tag rather than nothing: a Select used as a badge is a category even when
    it is not a status — `Personal`/`Commercial`, `Percent`/`Amount` — and a row
    of badges where half carry an icon and half do not reads as broken rather
    than as varied.
    """
    text = (title or "").strip().lower()
    for icon, words in STATE_ICON_WORDS:
        if any(word in text for word in words):
            return icon
    return "lucide-tag"


# --------------------------------------------------------------------------- #
# Tab icons
#
# Every tab in OneSpace carries a glyph, and none of them is declared.
#
# Frappe has no icon property on a Tab Break — a doctype's tabs are a label and
# nothing else — and the tabs we draw over a record are ours. So the glyph is
# derived from the tab's own words, exactly the way a status's is, and for the
# same reason: a doctype we do not own (ERPNext's) will never have a manifest
# entry and should still get something better than a blank.
#
# Closed set, written as literals, because Tailwind emits CSS only for class
# names it can find in the source. See SPACE_ICONS.
# --------------------------------------------------------------------------- #

TAB_ICONS = [
    "lucide-list",           # details, the first tab of almost everything
    "lucide-link",           # connections, related records
    "lucide-info",           # more information
    "lucide-sticky-note",    # notes, remarks
    "lucide-message-circle",  # comments
    "lucide-history",        # history, changes
    "lucide-activity",       # activity, timeline
    "lucide-paperclip",      # files, attachments
    "lucide-settings",       # settings, preferences, advanced
    "lucide-shield",         # permissions, roles, access
    "lucide-users",          # people, contacts, members
    "lucide-map-pin",        # address, region
    "lucide-calculator",     # accounting, tax
    "lucide-banknote",       # payments, pricing, billing
    "lucide-calendar",       # dates, schedule
    "lucide-package",        # items, stock
    "lucide-file-text",      # terms, printing, content
    "lucide-mail",           # email
    "lucide-bell",           # notifications, alerts
    "lucide-plug",           # integrations, api, webhooks
    "lucide-ruler",          # dimensions, measurements
    "lucide-panel-top",      # a tab, and nothing more specific
]

DEFAULT_TAB_ICON = "lucide-panel-top"

# Which glyph a tab's own words earn, in order — first match wins.
#
# Ordered by how specific the words are rather than alphabetically: `Payment
# Terms` is about money before it is about a document, and `Email Alerts` is a
# notification before it is a mailbox.
TAB_ICON_WORDS = [
    ("lucide-link", ("connection", "link", "related", "reference")),
    ("lucide-history", ("history", "changes", "audit", "log", "version",
                        "revision")),
    ("lucide-activity", ("activity", "timeline", "event")),
    ("lucide-message-circle", ("comment", "discussion", "feedback", "reply")),
    ("lucide-paperclip", ("file", "attachment", "document", "upload")),
    ("lucide-shield", ("permission", "role", "access", "security", "sharing")),
    ("lucide-bell", ("notification", "alert", "reminder", "subscriber")),
    ("lucide-mail", ("email", "mail", "inbox", "message")),
    ("lucide-plug", ("integration", "api", "webhook", "connector", "sync")),
    ("lucide-banknote", ("payment", "pricing", "price", "billing", "currency",
                         "invoice", "credit", "cost", "rate", "amount",
                         "commission", "discount")),
    ("lucide-calculator", ("accounting", "account", "tax", "total", "charge",
                           "ledger")),
    ("lucide-package", ("item", "product", "stock", "inventory", "material",
                        "warehouse", "delivery", "shipping")),
    ("lucide-map-pin", ("address", "location", "region", "territory")),
    ("lucide-users", ("contact", "people", "member", "team", "user", "party",
                      "participant", "attendee", "guest", "customer",
                      "supplier", "employee", "assign")),
    ("lucide-calendar", ("date", "schedule", "timing", "period")),
    ("lucide-ruler", ("dimension", "measurement", "size", "weight")),
    ("lucide-sticky-note", ("note", "remark", "description", "summary")),
    ("lucide-settings", ("setting", "preference", "configuration", "option",
                         "advanced", "rule")),
    # Before the printing words, because "information" contains "form" and a
    # tab called More Information is not a print format.
    ("lucide-info", ("information", "about", "misc", "other")),
    ("lucide-file-text", ("print", "template", "content", "text", "letter",
                          "legal", "term", "condition")),
    ("lucide-list", ("detail", "general", "overview", "main", "basic",
                     "primary")),
]


def tab_icon(label: str) -> str:
    """The glyph a tab's words earn, or the neutral panel.

    Never nothing. A strip where three tabs carry an icon and the fourth does
    not reads as a tab that failed to load, which is the same argument
    `state_icon` makes about a row of badges.
    """
    text = (label or "").strip().lower()
    for icon, words in TAB_ICON_WORDS:
        if any(word in text for word in words):
            return icon
    return DEFAULT_TAB_ICON


# --------------------------------------------------------------------------- #
# Activity glyphs
#
# One timeline over a record, and every entry on it says what kind of thing it
# is before it says anything else. A comment and a field change are different
# events and a column of identical avatars makes them look like the same one.
#
# A fourth closed set, closed for the same build-time reason as the other
# three: Tailwind emits CSS only for class names it finds as literals.
# --------------------------------------------------------------------------- #

ACTIVITY_ICONS = {
    # The record itself, which is where every timeline starts. Without it the
    # oldest thing on a record is whatever somebody happened to do to it next.
    "created": "lucide-circle-plus",
    "comment": "lucide-message-circle",
    "change": "lucide-pencil",
}

DEFAULT_ACTIVITY_ICON = "lucide-dot"


def activity_icon(kind: str) -> str:
    """The glyph for one kind of timeline entry."""
    return ACTIVITY_ICONS.get(kind or "", DEFAULT_ACTIVITY_ICON)


# --------------------------------------------------------------------------- #
# Notification glyphs
#
# Keyed by `Notification Type`, which is a doctype and therefore open: a space,
# or a site, may add one. So this is a *known* set rather than a closed one —
# a type nobody has drawn gets the default bell, which is the honest rendering
# of "something happened that we have no picture for".
#
# Still literals, for the fifth time and the same build-time reason: Tailwind
# emits CSS only for class names it can find in the source.
# --------------------------------------------------------------------------- #

NOTIFICATION_ICONS = {
    # Frappe's own built-ins, seeded by the framework on every site.
    "Mention": "lucide-at-sign",
    "Assignment": "lucide-user-check",
    "Share": "lucide-share-2",
    "Alert": "lucide-triangle-alert",
    "Energy Point": "lucide-zap",
}

DEFAULT_NOTIFICATION_ICON = "lucide-bell"


def notification_icon(kind: str) -> str:
    """The glyph for one kind of notification."""
    return NOTIFICATION_ICONS.get(kind or "", DEFAULT_NOTIFICATION_ICON)
