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
