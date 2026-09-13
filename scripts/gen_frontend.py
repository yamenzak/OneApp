"""Generate the frontend setup for every SPA in the monorepo.

Two SPAs — the tenant app and the admin control plane — must look and behave
like one product. The risk is drift: two Vite configs, two Tailwind setups, two
different ideas of which components are allowed, diverging a little at a time.

They cannot share an npm workspace, because each app is mirrored to its own
repository for Frappe Cloud and has to be self-contained. So the shared setup is
*generated* into both instead, from the single definition in `scripts/spa/`,
exactly as the doctypes are. `scripts/check_frontend.py` fails CI if either copy
is edited by hand.

This file is the assembly: which generated file gets which content, and which
bundle gets which files. The content itself lives in `scripts/spa/`, a module
per concern. Names are re-exported here because `from gen_frontend import APPS`
is how the guards and `check_frontend.py` have always reached them.

Run: python3 scripts/gen_frontend.py
"""

import os

from spa.spec import (
    APPS, BANNER, BRAND, DEPENDENCIES, DEV_DEPENDENCIES, ROOT, rewrite, where,
)
from spa.ui import UI_BARREL
from spa.runtime import (
    BOOT_JS, BRAND_JS, DATES_JS, ERRORS_JS, FORMAT_JS, NOTIFY_JS, RESOURCE_JS,
    REMEMBER_JS, SIZE_JS, SOCKET_JS, SOUND_JS, TRANSLATE_JS,
)
from spa.shell import (
    APP_SHELL_VUE, EMPTY_STATE_VUE, THEME_SETTING_VUE, USAGE_BAR_VUE,
    USER_MENU_VUE,
)
from spa.screens import (
    APPEARANCE_JS, ICONS_JS, LIST_COLUMNS_JS, BREAKPOINT_JS, SETTINGS_GEOMETRY_JS,
    USER_JS,
)
from spa.build import (
    app_root_package_json, eslint_config, index_html, package_json,
    postcss_config, tailwind_config, vite_config,
)
from spa.browser import E2E_AUTH_JS, SHOT_MJS, playwright_config, shot_mjs
from spa.surface import PANEL_VUE, ROW_STATE_JS, ROW_VUE
from spa.fields import fields_js


# What any bundle needs: the build, the component barrel, and the request layer
# every call goes through. A page that fetches nothing at all would still want
# most of this, because the toast an error becomes is part of the request layer.
FILES = {
    "index.html": index_html,
    "vite.config.js": vite_config,
    "tailwind.config.js": lambda app, spec: tailwind_config(app),
    "postcss.config.js": lambda app, spec: postcss_config(app),
    "package.json": package_json,
    "eslint.config.js": lambda app, spec: eslint_config(app),
    "src/ui.js": lambda app, spec: UI_BARREL,
    "src/components/Panel.vue": lambda app, spec: PANEL_VUE,
    "src/lib/rowstate.js": lambda app, spec: ROW_STATE_JS,
    "src/components/Row.vue": lambda app, spec: ROW_VUE,
    "src/lib/runtime/boot.js": lambda app, spec: BOOT_JS,
    "src/lib/runtime/errors.js": lambda app, spec: ERRORS_JS,
    "src/lib/runtime/sound.js": lambda app, spec: SOUND_JS,
    "src/lib/url/remember.js": lambda app, spec: REMEMBER_JS,
    "src/lib/runtime/notify.js": lambda app, spec: NOTIFY_JS,
    "src/lib/runtime/socket.js": lambda app, spec: SOCKET_JS,
    "src/lib/runtime/resource.js": lambda app, spec: RESOURCE_JS,
    "src/lib/runtime/brand.js": lambda app, spec: BRAND_JS,
    "src/lib/runtime/translate.js": lambda app, spec: TRANSLATE_JS,
    "src/lib/runtime/dates.js": lambda app, spec: DATES_JS,
    "src/lib/runtime/format.js": lambda app, spec: FORMAT_JS,
    "src/lib/files/size.js": lambda app, spec: SIZE_JS,
    "playwright.config.js": playwright_config,
    "e2e/auth.js": lambda app, spec: E2E_AUTH_JS,
    "shot.mjs": shot_mjs,
}

# What a bundle needs only if it renders the shell: a rail, a bottom bar, an
# account menu, a settings dialog, screens over doctypes.
#
# `oneapp_control` is a signup page and nothing else, and generating these into
# it produced an AppShell no route mounted and a settings dialog over no
# settings — dead files that the guards then read as a second navigation surface
# to keep in step. A bundle asks for this family by declaring `shell` in APPS.
SHELL_FILES = {
    "src/components/EmptyState.vue": lambda app, spec: EMPTY_STATE_VUE,
    "src/components/UserMenu.vue": lambda app, spec: USER_MENU_VUE,
    "src/components/UsageBar.vue": lambda app, spec: USAGE_BAR_VUE,
    "src/lib/shell/breakpoint.js": lambda app, spec: BREAKPOINT_JS,
    "src/lib/shell/appearance.js": lambda app, spec: APPEARANCE_JS,
    "src/lib/screen/list.js": lambda app, spec: LIST_COLUMNS_JS,
    "src/lib/screen/fields.js": fields_js,
    "src/components/settings/geometry.js": lambda app, spec: SETTINGS_GEOMETRY_JS,
    "src/lib/shell/icons.js": lambda app, spec: ICONS_JS,
    "src/lib/shell/user.js": lambda app, spec: USER_JS,
    "src/components/AppShell.vue": lambda app, spec: APP_SHELL_VUE,
    "src/components/ThemeSetting.vue": lambda app, spec: THEME_SETTING_VUE,
}

# Written to the app repository root rather than into frontend/.
ROOT_FILES = {
    "package.json": app_root_package_json,
}


def render(app: str, spec: dict) -> dict:
    """Every generated path, relative to apps/<app>/.

    The keys below are written in the flat layout — `src/lib/runtime/boot.js` —
    because that is the layout this shared setup was born in and renaming every
    one of them would say nothing the table in `spa/spec.py` does not. A bundle
    that keeps things somewhere else says so once, there, and both the path and
    the `@/…` imports inside the text follow from the same table. They cannot
    disagree, which is the only reason to do it this way rather than by hand.
    """
    files = dict(FILES)
    if spec.get("shell"):
        files.update(SHELL_FILES)
    out = {
        f"frontend/{where(app, name)}": rewrite(app, fn(app, spec))
        for name, fn in files.items()
    }
    out.update({name: fn(app, spec) for name, fn in ROOT_FILES.items()})
    return out


def main():
    written = []
    for app, spec in APPS.items():
        base = os.path.join(ROOT, "apps", app)
        for name, content in render(app, spec).items():
            path = os.path.join(base, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(content)
            written.append(f"{app}/{name}")

    print(f"{len(written)} files across {len(APPS)} apps")
    for w in written:
        print(f"  {w}")


if __name__ == "__main__":
    main()
