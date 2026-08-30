"""Every frappe-ui prop and slot we pass must be one the component declares.

This is the guard for the whole family of bugs found by looking at the app
rather than by running its tests:

* `<PageHeader>` filled `#title` and `#actions`; it has only a default slot, so
  eight pages rendered an empty header bar.
* `<SettingsNavItem :label>` — the label is the default slot, so the settings
  nav showed icons and no words.
* `<SettingsRow :label>` — the prop is `title`, so every field lost its name.
* `<ListRows>` with a `v-for` child and no `:items` — every list rendered zero
  rows while the count beside it stayed correct.

None of them threw. Vue turns an unknown prop into a fallthrough attribute and
never renders an unknown slot, so the page loads and the thing is simply
missing. Only reading the declarations catches it, so that is what this does.
"""

import re
from pathlib import Path

import pytest

from frappe_ui_api import NOT_PROPS, ROOT, UI_SRC, component_api

APPS = ("oneapp", "oneapp_control")
API = component_api()

# Tags in our templates that are ours, not frappe-ui's.
#
# The attribute run consumes quoted values whole rather than stopping at the
# first `>`, because `v-if="tabs.length > 1"` is ordinary Vue and cutting the
# tag there left `tabs.length` looking like a bare attribute — reported as a
# prop `Tabs` does not take. A guard that has to be written around is a guard
# people write around.
TAG = re.compile(
    r"""<(/?)([A-Z][A-Za-z0-9]*)\b((?:"[^"]*"|'[^']*'|[^>"'])*?)(/?)>""", re.S
)
SLOT = re.compile(r"<template\s+(?:#|v-slot:)([A-Za-z0-9_-]+)")
# Attribute *names*, with any quoted value consumed so the scan never treats
# class names or expression text as further attributes.
ATTR = re.compile(
    r"""(?P<name>[@:#]?[A-Za-z_][\w:.\-]*)"""
    r"""(?:\s*=\s*(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'))?"""
)

# A binding whose branches are string literals: `a ? 'green' : 'red'`. Split on
# the ternary punctuation outside quotes; a segment that is exactly a quoted
# string is a value the prop can actually take, while `x === 'blocking'` is a
# comparison and stays part of a larger segment.
LITERAL = re.compile(r"""^\s*(?:'([^']*)'|"([^"]*)")\s*$""")


def written_values(attr: str, raw: str | None) -> set[str]:
    """The literal values an attribute can pass, or an empty set if unknowable."""
    if raw is None:
        return set()
    # `v-model="scheme"` binds a variable named scheme; it does not pass the
    # string "scheme". Reading it as a literal reported every v-model as an
    # out-of-range value.
    if not attr.startswith((":", "v-bind:", "v-model")):
        return {raw}

    segments, current, quote = [], [], None
    for char in raw:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            current.append(char)
        elif char in "?:":
            segments.append("".join(current))
            current = []
        else:
            current.append(char)
    segments.append("".join(current))

    values = set()
    for segment in segments:
        m = LITERAL.match(segment)
        if m:
            values.add(m.group(1) if m.group(1) is not None else m.group(2))
    return values


def sources(app: str):
    root = ROOT / f"apps/{app}/frontend/src"
    return {p.relative_to(root).as_posix(): p.read_text() for p in root.rglob("*.vue")}


def normalise(attr: str) -> str | None:
    """The prop an attribute maps to, or None when it is not a prop at all."""
    if attr.startswith("@") or attr.startswith("v-on:"):
        return None
    if attr.startswith("v-model"):
        # v-model → modelValue; v-model:open → open.
        _, _, arg = attr.partition(":")
        return arg or "modelValue"
    attr = re.sub(r"^(:|v-bind:)", "", attr)
    if attr == "v-bind" or NOT_PROPS.match(attr):
        return None
    # Templates are kebab-case, declarations camelCase.
    return re.sub(r"-([a-z])", lambda m: m.group(1).upper(), attr)


def usages(source: str):
    """Yield {component, props, slots} for each frappe-ui element in a file.

    One linear scan with a stack of *all* components, ours included. Attributing
    a slot to the innermost frappe-ui element instead would blame a parent for
    `#prefix` on our own component nested inside it — the guard's first run did
    exactly that and reported four things that were fine.
    """
    stack, found = [], []
    events = []
    for m in TAG.finditer(source):
        events.append(("tag", m))
    for m in SLOT.finditer(source):
        events.append(("slot", m))
    events.sort(key=lambda e: e[1].start())

    for kind, match in events:
        if kind == "slot":
            # A <template #x> belongs to whatever element encloses it.
            if stack:
                stack[-1]["slots"].add(match.group(1))
            continue

        closing, name, attrs, self_closing = match.groups()

        if closing:
            while stack and stack[-1]["component"] != name:
                stack.pop()
            if stack:
                entry = stack.pop()
                entry["content"] = source[entry["start"] : match.start()]
                found.append(entry)
            continue

        entry = {
            "component": name,
            "props": set(),
            "values": {},
            "slots": set(),
            "spreads": False,
            "content": "",
            "start": match.end(),
        }
        if name in API:
            for m in ATTR.finditer(attrs):
                raw = m.group("name")
                if raw in ("v-bind", "v-html") or raw.startswith("v-bind="):
                    entry["spreads"] = True
                prop = normalise(raw)
                if prop:
                    entry["props"].add(prop)
                    written = written_values(raw, m.group("double") or m.group("single"))
                    if written:
                        entry["values"].setdefault(prop, set()).update(written)

        if self_closing:
            found.append(entry)
        else:
            stack.append(entry)

    found.extend(stack)
    return [e for e in found if e["component"] in API]


# Components that pass undeclared attributes to something inside them, and the
# attributes they are actually expected to be given that way. An allowlist
# rather than a blanket exemption: `useAttrs()` is common enough in frappe-ui
# that skipping every component using it turned the check off for Button,
# Dropdown, Avatar, Tooltip and the whole form-control family. That is how
# `<Dropdown placement="top-start">` survived — frappe-ui removed `placement`
# in 1.0 and warns about it in dev, and the menu had been unpositioned since.
FORWARDED = {
    # Documented as forwarding the inner control's own attributes: `options`
    # for a select, `min`/`max`/`rows` for the pickers and textarea.
    # `v-model` and `placeholder` reach the inner control the same way `options`
    # does — frappe-ui's own ProfilePanel story writes
    # `<FormControl label="Full name" v-model="fullName" />`.
    "FormControl": {
        "modelValue", "placeholder", "options", "min", "max",
        "rows", "step", "debounce", "autocomplete", "disabled",
    },
    "TextInput": {"min", "max", "step", "autocomplete", "inputmode", "maxlength", "readonly"},
    "Textarea": {"rows", "maxlength", "readonly"},
    "Select": {"multiple"},
    "Avatar": {"alt"},
    # Forwards to the trigger Button it renders when given no #trigger slot.
    "Dropdown": {"variant", "theme", "size", "loading", "icon", "iconLeft", "iconRight"},
}


@pytest.mark.parametrize("app", APPS)
def test_no_unknown_props(app):
    problems = []
    for path, source in sources(app).items():
        for use in usages(source):
            entry = API[use["component"]]
            declared = entry["props"] | FORWARDED.get(use["component"], set())
            if entry["forwards"] and not declared:
                continue
            # A component that declares no props at all is still checked. The
            # opposite — skipping it as "nothing to compare against" — is how
            # `<ListHeaderCell :label="c" />` survived on four pages: the label
            # is ListHeaderCell's default slot, so every column header was blank.
            unknown = use["props"] - declared
            if unknown:
                problems.append(
                    f"{app}/{path}: <{use['component']}> does not take "
                    f"{sorted(unknown)} — it takes {sorted(declared)}"
                )
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("app", APPS)
def test_prop_values_are_in_range(app):
    """A value outside a prop's union is ignored, and the default renders.

    `<Badge theme="orange">` is not a warning — Badge's themes are
    gray|blue|green|amber|red|violet, so the badge came out grey and the "3
    blockers" pill read as ordinary chrome rather than as something wrong.
    """
    problems = []
    for path, source in sources(app).items():
        for use in usages(source):
            allowed = API[use["component"]]["enums"]
            for prop, written in use["values"].items():
                if prop not in allowed:
                    continue
                outside = written - allowed[prop]
                if outside:
                    problems.append(
                        f"{app}/{path}: <{use['component']} {prop}> cannot be "
                        f"{sorted(outside)} — only {sorted(allowed[prop])}"
                    )
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("app", APPS)
def test_no_unknown_slots(app):
    problems = []
    for path, source in sources(app).items():
        for use in usages(source):
            declared = API[use["component"]]["slots"]
            unknown = use["slots"] - declared
            if unknown:
                problems.append(
                    f"{app}/{path}: <{use['component']}> has no slot "
                    f"{sorted(unknown)} — it has {sorted(declared) or 'none'}"
                )
    assert not problems, "\n".join(problems)


# Everything that is not the default slot: named-slot templates, comments, and
# the `v-if`/`v-for` a wrapper element might carry.
NAMED_SLOT_BLOCK = re.compile(r"<template\s+(?:#|v-slot:)[^>]*>.*?</template>", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def default_slot_content(source: str) -> str:
    """What a component's children would render into its default slot."""
    text = NAMED_SLOT_BLOCK.sub("", COMMENT.sub("", source))
    return text.strip()


@pytest.mark.parametrize("app", APPS)
def test_content_goes_somewhere(app):
    """Children handed to a component that has no default slot render nowhere.

    Alert is the case that got past every other check here: it declares `title`,
    `description`, `prefix` and `actions`, and no default slot. Nine
    `<Alert …>body text</Alert>` blocks passed the prop check, passed the slot
    check — the body is not a named slot — and dropped their text on the floor.
    """
    problems = []
    for path, source in sources(app).items():
        for use in usages(source):
            entry = API[use["component"]]
            if "default" in entry["slots"] or not entry["slots"]:
                continue
            if default_slot_content(use["content"]):
                problems.append(
                    f"{app}/{path}: <{use['component']}> has no default slot, so its "
                    f"content renders nowhere — its slots are {sorted(entry['slots'])}"
                )
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("app", APPS)
def test_required_props_are_passed(app):
    """A missing required prop is silent too.

    `<ListRows>` without `:items` renders zero rows, beside a count that still
    reads correctly off the same array — which is exactly how eight empty lists
    shipped.
    """
    problems = []
    for path, source in sources(app).items():
        for use in usages(source):
            if use["spreads"]:
                # v-bind="obj" can supply anything; nothing can be concluded.
                continue
            missing = API[use["component"]]["required"] - use["props"]
            if missing:
                problems.append(
                    f"{app}/{path}: <{use['component']}> is missing required "
                    f"{sorted(missing)}"
                )
    assert not problems, "\n".join(problems)


# frappe-ui declares its components four different ways, and a reader that
# handles only some of them reports the rest as taking nothing — which reads
# exactly like a clean run. Each entry here is one of those forms, so a parser
# that quietly stops understanding one fails loudly instead.
#
#   Badge          `defineProps<{ … }>()`, an inline literal
#   SidebarHeader  `defineProps<SidebarHeaderProps>()`, a named type in types.ts
#   Alert          `defineProps(alertProps)`, a runtime props object
#   Button         `defineComponent({ props: buttonProps })`, the options API
#   SettingsDialog `defineModel('open')`, a named v-model
DECLARATION_FORMS = {
    "Badge": {"label", "size", "theme", "variant"},
    "SidebarHeader": {"title", "subtitle", "logo", "showLogo", "menuItems"},
    "Alert": {"title", "description", "theme", "icon", "dismissible",
              "primaryAction", "secondaryAction"},
    "Button": {"label", "variant", "theme", "size", "loading", "disabled",
               "icon", "iconLeft", "iconRight", "link", "route", "tooltip",
               "type", "loadingText"},
    "SettingsDialog": {"open", "tab", "size", "shortcut", "unmountOnHide"},
}


def test_the_reader_found_frappe_ui():
    # If the package moves, every assertion above passes for the wrong reason.
    assert UI_SRC.exists(), f"{UI_SRC} is missing — install frontend dependencies"
    assert len(API) > 100, f"only parsed {len(API)} components; the declarations moved"
    assert API["PageHeader"]["slots"] == {"default"}


@pytest.mark.parametrize("component,expected", sorted(DECLARATION_FORMS.items()))
def test_the_reader_understands_every_declaration_form(component, expected):
    assert API[component]["props"] == expected


def test_the_reader_ignores_commented_out_declarations():
    # SidebarHeader's comment quotes `defineProps<{ showLogo?: boolean }>()` to
    # explain why the real declaration is written differently. Reading the
    # comment gave the component exactly one prop and hid the other four.
    assert "subtitle" in API["SidebarHeader"]["props"]


def test_the_reader_does_not_follow_imports():
    # `import { type AlertSlots } from './types'` matched the declaration
    # pattern before it was anchored to the start of a line, and the resolver
    # walked into whatever followed the import instead.
    assert "title" in API["Alert"]["slots"]
    assert "dismiss" not in API["Alert"]["slots"]


# Every surface the product has, and a file that must exist on each. The guards
# above sweep `apps/*/frontend/src`, which covers all of them today — but
# "today" is the problem: a fourth surface added under a path this sweep does
# not reach would be unguarded and nothing would say so. These are the surfaces
# in the product, named, so adding one means coming here.
SURFACES = {
    "oneapp": {
        "the tenant workspace (OneSpace)": "pages/Launcher.vue",
    },
    "oneapp_control": {
        "the operator console (OneAdmin)": "pages/Tenants.vue",
        "customer self-service": "pages/account/AccountOverview.vue",
        "signup": "pages/signup/SignupPage.vue",
    },
}


@pytest.mark.parametrize(
    "app,surface,witness",
    [(app, s, w) for app, items in SURFACES.items() for s, w in items.items()],
)
def test_every_surface_is_swept(app, surface, witness):
    files = sources(app)
    assert witness in files, f"{surface}: {witness} is not where the guards look"


@pytest.mark.parametrize("app", APPS)
def test_the_sweep_reaches_pages_and_components(app):
    files = sources(app)
    assert any(p.startswith("pages/") for p in files), f"{app}: no pages swept"
    assert any(p.startswith("components/") for p in files), f"{app}: no components swept"


def test_the_sweep_descends_into_subdirectories():
    """A shallow glob would still find pages/ and components/ and look fine.

    Only the control app nests today — `pages/account`, `pages/signup`,
    `components/settings` — which is exactly where self-service and signup live.
    """
    nested = [p for p in sources("oneapp_control") if p.count("/") >= 2]
    assert len(nested) >= 3, f"nested files not swept: {nested}"


def test_icons_use_the_component_s_own_icon_prop():
    """`Icon` is for icons outside a component's icon prop, says its own page.

    Three sidebars filled `#prefix` with a bare `<Icon>` on a `SidebarItem`,
    which declares `icon` and renders it through SidebarItemIcon — at the
    library's ink tone rather than whichever one the call site picked. The slot
    is for something an icon prop cannot express: an avatar, a badge, a stack.
    """
    bare_icon = re.compile(
        r"<template\s+#(prefix|suffix)>\s*<Icon\b[^>]*/>\s*</template>", re.S
    )
    problems = []
    for app in APPS:
        for path, source in sources(app).items():
            for use in usages(source):
                declared = API[use["component"]]["props"]
                for match in bare_icon.finditer(use["content"]):
                    slot = match.group(1)
                    wanted = {"prefix": ("icon", "iconLeft"), "suffix": ("icon", "iconRight")}[slot]
                    options = [p for p in wanted if p in declared]
                    if options:
                        problems.append(
                            f"{app}/{path}: <{use['component']} #{slot}> holds only an "
                            f"<Icon>; it declares {' / '.join(options)}"
                        )
    assert not problems, "\n".join(problems)


def test_shadows_pair_with_an_elevation_surface():
    """From the Elevation page's own pairing table.

    Shadows fade against dark backgrounds, so in dark mode depth comes from a
    lighter surface instead. `surface-elevation-*` stays white in light mode and
    steps lighter in dark; a raw `surface-gray-*` under a shadow is flat in one
    of the two themes.
    """
    shadow = re.compile(r"\bshadow-(sm|base|md|lg|xl|2xl)\b")
    problems = []
    for app in APPS:
        root = ROOT / f"apps/{app}/frontend/src"
        for path in sorted(root.rglob("*.vue")):
            for line in path.read_text().split("\n"):
                if shadow.search(line) and "surface-elevation" not in line:
                    if re.search(r"\bbg-surface-(?!elevation)", line):
                        problems.append(
                            f"{app}/{path.relative_to(root)}: {line.strip()[:90]}"
                        )
    assert not problems, "\n".join(problems)
