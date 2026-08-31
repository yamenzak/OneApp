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
