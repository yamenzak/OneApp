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
TAG = re.compile(r"<(/?)([A-Z][A-Za-z0-9]*)\b([^>]*?)(/?)>", re.S)
SLOT = re.compile(r"<template\s+(?:#|v-slot:)([A-Za-z0-9_-]+)")
# Attribute *names*, with any quoted value consumed so the scan never treats
# class names or expression text as further attributes.
ATTR = re.compile(
    r"""(?P<name>[@:#]?[A-Za-z_][\w:.\-]*)\s*(?:=\s*(?:"[^"]*"|'[^']*'))?"""
)


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

        if self_closing:
            found.append(entry)
        else:
            stack.append(entry)

    found.extend(stack)
    return [e for e in found if e["component"] in API]


@pytest.mark.parametrize("app", APPS)
def test_no_unknown_props(app):
    problems = []
    for path, source in sources(app).items():
        for use in usages(source):
            entry = API[use["component"]]
            if entry["forwards"]:
                # Forwards the rest to an inner element, so its surface is wider
                # than its declarations and "unknown" means nothing here.
                continue
            declared = entry["props"]
            if not declared:
                # No declarations and no forwarding: anything passed lands on
                # the root element instead of doing what was intended.
                continue
            unknown = use["props"] - declared
            if unknown:
                problems.append(
                    f"{app}/{path}: <{use['component']}> does not take "
                    f"{sorted(unknown)} — it takes {sorted(declared)}"
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
