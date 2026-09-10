"""What the two SPAs are.

Every other module in this package reads from here: which apps exist, where
each one mounts, which npm versions both are pinned to, and the banner that
marks a file as generated. One definition, so the tenant app and the control
plane cannot disagree about a version or a route.
"""

import os


# The repository root, two levels up: scripts/spa/spec.py -> scripts/ -> here.
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


# frappe-ui 1.x is Vite 7 / Tailwind 3 / vue-router 4. Pinned in one place so the
# two apps can never disagree about a version.
DEPENDENCIES = {
    "frappe-ui": "^1.0.0-beta.55",
    "socket.io-client": "^4.8.1",
    "vue": "^3.5.13",
    "vue-router": "^4.5.0",
}


# A package only one bundle needs is declared as `packages` on its entry below.
# Shared pins stay above; something one product uses does not belong in a list
# whose point is that the two apps agree.


DEV_DEPENDENCIES = {
    # The browser pass. Both SPAs get one: the bugs it catches — an empty list,
    # a dialog that will not open, a panel unreachable at one viewport — all
    # render without throwing, so a clean build says nothing about them.
    "@playwright/test": "^1.49.0",
    "@vitejs/plugin-vue": "^6.0.0",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.17.0",
    "eslint-plugin-vue": "^9.32.0",
    # What `no-undef` is told a browser already has. It arrives under eslint
    # anyway, but a rule that fails open — every `window` an error — should not
    # depend on somebody else's dependency tree.
    "globals": "^13.24.0",
    "postcss": "^8.5.0",
    "tailwindcss": "^3.4.17",
    "vite": "^7.0.0",
}


# The repositories and Frappe apps stay oneapp / oneapp_control — renaming those
# would move every import path and every mirror. What customers see is separate,
# and lives here so a rename is one edit rather than a hunt.
#
# One entry, and it used to be two. "OneAdmin" named the operator console at
# `/admin`; the console is a Space inside OneSpace now, so there is no second
# product for a customer or an operator to be looking at, and a constant nothing
# titles is a name waiting to be put back on something by mistake. The control
# plane is `oneapp_control`, which is an app, not a place.
BRAND = {"tenant": "OneSpace"}


APPS = {
    "oneapp": {
        "route": "/one",
        "title": BRAND["tenant"],
        # Two SPAs, two sites, both running at once — see scripts/dev.sh.
        "site": "space.localhost",
        "port": 8001,
        # Doctypes to generate TypeScript definitions for.
        "types": {"oneapp": ["OneSpace Site State"]},
        # The shell family: the rail, the bottom bar, the account menu, the
        # settings dialog. Every signed-in surface either audience has is a
        # Space in here, so this is the only bundle that renders one.
        "shell": True,
        "packages": {
            # Still here for the grid this vendoring replaces; it goes when
            # that grid does.
            "fast-formula-parser": "^1.0.19",
            # Reading and writing real spreadsheet files. Loaded with a dynamic
            # `import` and nowhere else, so its 900KB is paid by the person who
            # presses Import or Download as Excel. SheetJS would have been the
            # obvious pick and is not: the newest release on npm is 0.18.5 and
            # carries two advisories fixed only on the project's own CDN.
            "exceljs": "^4.4.0",
            # Charts on a sheet. Same deal: behind a dynamic import, paid for
            # by the person who inserts one.
            "echarts": "^6.0.0",
            "vue-echarts": "^8.0.1",
            # Reading somebody else's mail safely. A message body is HTML
            # written by a stranger, and the two things that must happen to it
            # before it reaches a screen are not things to hand-roll: DOMPurify
            # strips what should never run, and the iframe-resizer pair lets the
            # body live in its own document — its `<style>` cannot reach our app
            # — while still growing the frame to its own height. See
            # `components/mail/reader/VENDORED.md`.
            # A bar chart down time, which is what a Gantt is. Frappe's own
            # package and MIT, so this is a dependency rather than a vendoring
            # — the AGPL obligations that come with taking code from
            # `frappe/*` do not apply to something published on npm under a
            # permissive licence. It draws into a plain element and takes a
            # list of {id, name, start, end, progress}, so the mapping is ours
            # and small: `components/screen/bodies/GanttBody.vue`.
            "frappe-gantt": "^1.2.2",
            # The map. BSD-3, so a dependency rather than a vendoring — the
            # AGPL obligations that come with taking code from `frappe/*` do
            # not apply to something published on npm under a permissive
            # licence. WebGL, which is what makes a thousand moving markers
            # possible at all, and behind a dynamic import so its weight is
            # paid by whoever opens a map. Its basemap is ours and self-hosted
            # (see `apps/oneapp/oneapp/onemobility/README.md` §7): no tile
            # request ever leaves for a third party, which is a privacy
            # position as much as a rendering one.
            "maplibre-gl": "^5.0.0",
            "dompurify": "^3.2.6",
            # The editor's own kit, named directly because the document editor
            # declares a node of its own — the record field, which is not text
            # but a fieldname rendered from the record the document is bound
            # to (`modules/onedoc/lib/recordField.js`). It arrives with
            # frappe-ui either way; declaring it says so, and pins the major
            # the node's API is written against. MIT.
            "@tiptap/core": "^3.30.5",
            "@iframe-resizer/child": "5.5.9",
            "@iframe-resizer/vue": "5.5.9",
            # Two people in one file. A CRDT is the only honest answer to two
            # cursors in one paragraph, and this is the one everybody uses —
            # MIT, browser-only, and no runtime of its own: what Frappe pays a
            # separate Node process for, `apps/oneapp/realtime/handlers.js`
            # does inside the socketio the bench already runs. See
            # `docs/COLLABORATION.md`.
            "yjs": "^13.6.32",
            # Awareness — where everybody's caret is — in the standard wire
            # format rather than a re-implementation of it. Frappe wrote their
            # own to avoid the dependency; we take it because Tiptap's caret
            # extension expects the real thing, and two awareness
            # implementations for two editors in one suite is drift.
            "y-protocols": "^1.0.7",
            # The document's half. `y-prosemirror` is what makes a paragraph
            # a CRDT rather than a string, and the two Tiptap extensions are
            # the binding and the carets. Pinned to the same major as
            # `@tiptap/core` above, because a ProseMirror plugin from a
            # different major shares no schema with the editor it is in.
            "y-prosemirror": "^1.3.7",
            "@tiptap/extension-collaboration": "^3.31.3",
            "@tiptap/extension-collaboration-caret": "^3.31.3",
        },
        # The spreadsheet engine and its canvas renderer are Frappe's, vendored
        # whole (see src/lib/sheets/VENDORED.md) — and their unit suite came
        # with them. The mail reader's asset blocking is the second thing here a
        # browser pass cannot reach: whether a tracking pixel loads is a
        # question about eight shapes of HTML, not about a screen.
        "dev_packages": {"vitest": "^2.1.0", "happy-dom": "^20.10.2"},
        # Every module's, wherever it keeps them. It used to name three
        # directories and that was already a list somebody had to remember to
        # add to; with a module per product it would have been eight.
        "unit_tests": "src/**/*.test.js",
        # Mirrors the Frappe modules — see `apps/oneapp/oneapp/modules.txt`.
        "layout": "modules",
    },
    # Signing up, and nothing else.
    #
    # This app served two full SPAs — /admin for operators and /portal for
    # customers. Both are Spaces now, rendered by `oneapp` on this same site,
    # so what is left is the one page somebody reaches *before* they have an
    # account: `/one` sends a Guest to sign in, correctly, and signup cannot.
    #
    # Kept as its own bundle rather than folded into the tenant app because the
    # two answer different questions about who may load them, and a route that
    # is open to Guest should be a small, obvious, separate thing.
    "oneapp_control": {
        "route": "/signup",
        "title": BRAND["tenant"],
        "site": "control.localhost",
        "port": 8000,
        "types": {"oneapp_control": ["Account Request", "Plan", "Region"]},
    },
}


BANNER = "// Generated by scripts/gen_frontend.py. Edit that, not this file.\n"


# --------------------------------------------------------------------------- #
# Where a bundle keeps things
# --------------------------------------------------------------------------- #

#: The two shapes an SPA in this repository has.
#:
#: `flat` is what both had: `src/components/`, `src/lib/<family>/`, `src/pages/`.
#: `modules` is the tenant app since it was split to mirror the Frappe modules —
#: a directory per product under `src/modules/`, and `src/shared/` for what more
#: than one of them needs.
#:
#: The control plane stays flat and should: it is a signup page. A layout is a
#: way of finding things, and there is nothing in it to find.
#:
#: Every entry maps a *generated* path to where that bundle puts it. The same
#: table rewrites the `@/…` imports inside the generated text, so a file and the
#: imports pointing at it can never disagree.
LAYOUTS = {
    "flat": {},
    # The whole tenant layout, not only the generated part. `rewrite` uses the
    # same table on the `@/…` imports inside generated text, and generated text
    # imports hand-written files — the shell imports `brand/SpaceFace.vue`. One
    # table, so a file and every import of it move together, and the guards can
    # ask it where something is rather than each carrying a path.
    "modules": {
        # Products
        "src/components/docs": "src/modules/onedoc/components",
        "src/components/sheets": "src/modules/onesheet/components",
        "src/components/code": "src/modules/onecode/components",
        "src/components/drive": "src/modules/onestorage/components",
        "src/components/mail": "src/modules/onemail/components",
        "src/components/diary": "src/modules/onecalendar/components",
        "src/lib/sheets": "src/modules/onesheet/lib",
        "src/lib/files": "src/modules/onestorage/lib",
        # The platform
        "src/components/screen": "src/modules/onespace/components/screen",
        "src/components/settings": "src/modules/onespace/components/settings",
        "src/components/notifications":
            "src/modules/onespace/components/notifications",
        "src/components/chat": "src/modules/onespace/components/chat",
        "src/components/shell": "src/modules/onespace/components/shell",
        "src/components/versions": "src/modules/onespace/components/versions",
        "src/lib/screen": "src/modules/onespace/lib/screen",
        "src/lib/shell": "src/modules/onespace/lib/shell",
        "src/screens": "src/modules/onespace/screens",
        "src/components/AppShell.vue": "src/modules/onespace/components/AppShell.vue",
        "src/components/AiMark.vue": "src/modules/onespace/components/AiMark.vue",
        "src/components/QuotaMeter.vue":
            "src/modules/onespace/components/QuotaMeter.vue",
        "src/components/SidebarCollapse.vue":
            "src/modules/onespace/components/SidebarCollapse.vue",
        "src/components/SidebarResizer.vue":
            "src/modules/onespace/components/SidebarResizer.vue",
        "src/components/SpaceSidebar.vue":
            "src/modules/onespace/components/SpaceSidebar.vue",
        "src/components/ThemeSetting.vue":
            "src/modules/onespace/components/ThemeSetting.vue",
        "src/components/UsageBar.vue": "src/modules/onespace/components/UsageBar.vue",
        "src/components/UserMenu.vue": "src/modules/onespace/components/UserMenu.vue",
        # The agreements
        "src/components/LegalGate.vue": "src/modules/onelegal/components/LegalGate.vue",
        # Shared: what more than one module needs and none of them owns
        "src/components/brand": "src/shared/components/brand",
        "src/components/EmptyState.vue": "src/shared/components/EmptyState.vue",
        "src/components/FadedScroll.vue": "src/shared/components/FadedScroll.vue",
        "src/components/Resizer.vue": "src/shared/components/Resizer.vue",
        "src/components/SharePanel.vue": "src/shared/components/SharePanel.vue",
        "src/lib/runtime": "src/shared/lib/runtime",
        "src/lib/brand": "src/shared/lib/brand",
        "src/lib/paper": "src/shared/lib/paper",
        "src/lib/workspace": "src/shared/lib/workspace",
        "src/composables": "src/shared/composables",
        # Pages, each with the module whose screen it is
        "src/pages/Doc.vue": "src/modules/onedoc/pages/Doc.vue",
        "src/pages/Sheet.vue": "src/modules/onesheet/pages/Sheet.vue",
        "src/pages/Drive.vue": "src/modules/onestorage/pages/Drive.vue",
        "src/pages/Mail.vue": "src/modules/onemail/pages/Mail.vue",
        "src/pages/Diary.vue": "src/modules/onecalendar/pages/Diary.vue",
        "src/pages/Chat.vue": "src/modules/onespace/pages/Chat.vue",
        "src/pages/Account.vue": "src/modules/onespace/pages/Account.vue",
        "src/pages/Launcher.vue": "src/modules/onespace/pages/Launcher.vue",
        "src/pages/Marketplace.vue": "src/modules/onespace/pages/Marketplace.vue",
        "src/pages/ScreenHost.vue": "src/modules/onespace/pages/ScreenHost.vue",
        "src/pages/NotFound.vue": "src/shared/pages/NotFound.vue",
    },
}


def moves(app: str) -> list[tuple[str, str]]:
    """One bundle's layout, longest source first so a prefix cannot win early."""
    table = LAYOUTS[APPS[app].get("layout", "flat")]
    return sorted(table.items(), key=lambda pair: -len(pair[0]))


def where(app: str, path: str) -> str:
    """A generated file's path in this bundle.

    Called with the flat path — which is the one the generator is written in,
    because that is the layout the shared setup was born in and renaming every
    key would say nothing extra.
    """
    for old, new in moves(app):
        if path == old or path.startswith(old + "/"):
            return new + path[len(old):]
    return path


def rewrite(app: str, text: str) -> str:
    """The same table, applied to `@/…` imports inside generated text."""
    for old, new in moves(app):
        text = text.replace("@/" + old[4:], "@/" + new[4:])
    return text
