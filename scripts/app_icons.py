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

# Grouped by what an app is, not by glyph, so the list stays choosable.
SPACE_ICONS = [
    "lucide-layout-grid",      # default / launcher
    "lucide-users",            # CRM, contacts
    "lucide-user-round",       # HR, people
    "lucide-briefcase",        # projects, work
    "lucide-file-text",        # documents, invoices
    "lucide-receipt",          # billing, expenses
    "lucide-wallet",           # finance, payments
    "lucide-shopping-cart",    # commerce, orders
    "lucide-package",          # inventory, stock
    "lucide-truck",            # logistics, delivery
    "lucide-factory",          # manufacturing
    "lucide-store",            # retail, POS
    "lucide-calendar",         # scheduling
    "lucide-clock",            # timesheets, attendance
    "lucide-message-square",   # chat, support
    "lucide-mail",             # email, campaigns
    "lucide-phone",            # telephony
    "lucide-chart-line",       # analytics, reports
    "lucide-chart-pie",        # dashboards
    "lucide-database",         # data, records
    "lucide-book-open",        # knowledge, docs
    "lucide-graduation-cap",   # training, LMS
    "lucide-stethoscope",      # healthcare
    "lucide-wrench",           # maintenance, service
    "lucide-shield",           # compliance, security
    "lucide-sparkles",         # AI, automation
]

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
    ("lucide-link", ("connection", "related", "reference", "linked")),
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
                      "customer", "supplier", "employee", "assign")),
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
