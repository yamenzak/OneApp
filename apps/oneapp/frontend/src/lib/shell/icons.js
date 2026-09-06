/**
 * The icons an app in the registry may use.
 *
 * These literals are what make the CSS exist. frappe-ui renders `lucide-*`
 * names as Tailwind utility classes, and the JIT only emits a class it can find
 * as a literal string — so an icon name that only ever exists in the database
 * renders as an empty box. The icons page gives two ways out: a known set
 * written as literals, or `~icons/lucide/*` imports for a genuinely open one. A
 * registry of apps we define is a known set.
 *
 * Never build an icon class by interpolation; the scanner cannot see it.
 *
 * Generated from scripts/app_icons.py, which also writes the doctype's Select
 * options, so the picker and the stored values cannot drift.
 */

export const SPACE_ICONS = [
  'lucide-layout-grid',
  'lucide-database',
  'lucide-sparkles',
  'lucide-shield',
  'lucide-users',
  'lucide-user-round',
  'lucide-graduation-cap',
  'lucide-stethoscope',
  'lucide-briefcase',
  'lucide-calendar',
  'lucide-clock',
  'lucide-wrench',
  'lucide-file-text',
  'lucide-receipt',
  'lucide-wallet',
  'lucide-shopping-cart',
  'lucide-package',
  'lucide-truck',
  'lucide-factory',
  'lucide-store',
  'lucide-message-square',
  'lucide-mail',
  'lucide-phone',
  'lucide-chart-line',
  'lucide-chart-pie',
  'lucide-book-open',
]

export const DEFAULT_SPACE_ICON = 'lucide-layout-grid'

/**
 * The same set, grouped, and with the words each icon answers to.
 *
 * The words were comments in `app_icons.py` before the picker had a search box,
 * which made them exactly as useful as no words at all: nobody looking for the
 * sales app types "chart line". Groups for the same reason — twenty-six glyphs
 * in one grid is a wall, and the same twenty-six under seven headings is a
 * list you can read.
 */
export const SPACE_ICON_GROUPS = [
  {
    "group": "General",
    "icons": [
      {
        "icon": "lucide-layout-grid",
        "words": [
          "grid",
          "launcher",
          "apps",
          "default",
          "home"
        ]
      },
      {
        "icon": "lucide-database",
        "words": [
          "data",
          "records",
          "storage",
          "table"
        ]
      },
      {
        "icon": "lucide-sparkles",
        "words": [
          "ai",
          "automation",
          "magic",
          "assistant"
        ]
      },
      {
        "icon": "lucide-shield",
        "words": [
          "compliance",
          "security",
          "policy",
          "audit"
        ]
      }
    ]
  },
  {
    "group": "People",
    "icons": [
      {
        "icon": "lucide-users",
        "words": [
          "crm",
          "contacts",
          "customers",
          "people",
          "team"
        ]
      },
      {
        "icon": "lucide-user-round",
        "words": [
          "hr",
          "people",
          "staff",
          "employee",
          "person"
        ]
      },
      {
        "icon": "lucide-graduation-cap",
        "words": [
          "training",
          "lms",
          "learning",
          "course"
        ]
      },
      {
        "icon": "lucide-stethoscope",
        "words": [
          "healthcare",
          "medical",
          "clinic",
          "patient"
        ]
      }
    ]
  },
  {
    "group": "Work",
    "icons": [
      {
        "icon": "lucide-briefcase",
        "words": [
          "projects",
          "work",
          "tasks",
          "jobs"
        ]
      },
      {
        "icon": "lucide-calendar",
        "words": [
          "scheduling",
          "calendar",
          "events",
          "bookings"
        ]
      },
      {
        "icon": "lucide-clock",
        "words": [
          "timesheets",
          "attendance",
          "hours",
          "time"
        ]
      },
      {
        "icon": "lucide-wrench",
        "words": [
          "maintenance",
          "service",
          "repairs",
          "field"
        ]
      }
    ]
  },
  {
    "group": "Money",
    "icons": [
      {
        "icon": "lucide-file-text",
        "words": [
          "documents",
          "invoices",
          "quotes",
          "papers"
        ]
      },
      {
        "icon": "lucide-receipt",
        "words": [
          "billing",
          "expenses",
          "receipts",
          "claims"
        ]
      },
      {
        "icon": "lucide-wallet",
        "words": [
          "finance",
          "payments",
          "accounts",
          "money"
        ]
      },
      {
        "icon": "lucide-shopping-cart",
        "words": [
          "commerce",
          "orders",
          "sales",
          "shop"
        ]
      }
    ]
  },
  {
    "group": "Goods",
    "icons": [
      {
        "icon": "lucide-package",
        "words": [
          "inventory",
          "stock",
          "items",
          "warehouse"
        ]
      },
      {
        "icon": "lucide-truck",
        "words": [
          "logistics",
          "delivery",
          "shipping",
          "fleet"
        ]
      },
      {
        "icon": "lucide-factory",
        "words": [
          "manufacturing",
          "production",
          "plant",
          "works"
        ]
      },
      {
        "icon": "lucide-store",
        "words": [
          "retail",
          "pos",
          "shop",
          "branch",
          "outlet"
        ]
      }
    ]
  },
  {
    "group": "Talking",
    "icons": [
      {
        "icon": "lucide-message-square",
        "words": [
          "chat",
          "support",
          "helpdesk",
          "tickets"
        ]
      },
      {
        "icon": "lucide-mail",
        "words": [
          "email",
          "campaigns",
          "newsletter",
          "inbox"
        ]
      },
      {
        "icon": "lucide-phone",
        "words": [
          "telephony",
          "calls",
          "phone",
          "dialer"
        ]
      }
    ]
  },
  {
    "group": "Numbers",
    "icons": [
      {
        "icon": "lucide-chart-line",
        "words": [
          "analytics",
          "reports",
          "trends",
          "metrics"
        ]
      },
      {
        "icon": "lucide-chart-pie",
        "words": [
          "dashboards",
          "insights",
          "breakdown",
          "share"
        ]
      },
      {
        "icon": "lucide-book-open",
        "words": [
          "knowledge",
          "docs",
          "wiki",
          "handbook",
          "notes"
        ]
      }
    ]
  }
]

/** Every icon whose name or words match, in group order. */
export function findSpaceIcons(query) {
  const text = String(query || '').trim().toLowerCase()
  return SPACE_ICON_GROUPS.map((group) => ({
    ...group,
    icons: group.icons.filter(
      (one) =>
        !text ||
        one.icon.includes(text) ||
        one.words.some((word) => word.includes(text)),
    ),
  })).filter((group) => group.icons.length)
}

/** A name we know renders — for anything stored before the set was narrowed. */
export function spaceIcon(name) {
  return SPACE_ICONS.includes(name) ? name : DEFAULT_SPACE_ICON
}
