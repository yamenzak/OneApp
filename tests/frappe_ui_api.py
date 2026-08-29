"""Read frappe-ui's own prop and slot declarations.

Every UI bug this session was the same mistake: passing a component a prop or a
slot it does not declare. Vue does not complain — an unknown prop becomes a
fallthrough attribute on the root element, and an unknown slot is simply never
rendered — so the page loads, nothing throws, and the thing is missing.

Guessing an API is cheap and reading one is cheaper, so this reads them.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT / "apps/oneapp_control/frontend/node_modules/frappe-ui/src"

# Attributes that are never props, whatever the component: Vue's own
# directives and the handful of attributes Vue itself consumes.
#
# Deliberately short. An earlier version also listed the common HTML attributes
# — `title`, `type`, `placeholder`, `disabled` — and that quietly disabled the
# checks for them: `title` is a real prop on Alert, Dialog, SidebarHeader and
# SettingsRow, so a missing one could never be reported. Passing a genuine DOM
# attribute to a component that does not declare it is itself worth knowing
# about, so the rest are checked like anything else.
NOT_PROPS = re.compile(
    r"^(v-if|v-else|v-else-if|v-for|v-show|v-html|v-text|v-pre|v-once|v-cloak"
    r"|v-slot|key|ref|class|style|is|slot|data-.*|aria-.*)$"
)

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"^[ \t]*//.*$", re.M)


def _script(source: str) -> str:
    """The component's script block, with comments removed.

    Both matter. frappe-ui documents its components in prose next to the code,
    and that prose quotes the very syntax being searched for — SidebarHeader's
    comment contains a literal `defineProps<{ showLogo?: boolean }>()` to
    explain why it is *not* written that way. Parsing the comment instead of the
    declaration is how this file came to believe SidebarHeader took one prop.
    """
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", source, re.S)
    text = "\n".join(blocks) if blocks else source
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))


def _members(block: str) -> dict[str, bool]:
    """{name: required} for a TypeScript object-type body.

    Nested object types are dropped first: `menuItems?: { label: string }[]`
    declares `menuItems`, not `label`.
    """
    flat, depth = [], 0
    for char in block:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif depth == 0:
            flat.append(char)
        elif char == "\n":
            flat.append(char)

    names = {}
    for line in "".join(flat).split("\n"):
        m = re.match(r"\s*([A-Za-z_$][\w$]*)\s*(\??)\s*:", line)
        if m:
            names[m.group(1)] = not m.group(2)
    return names


def _balanced(text: str, start: int) -> str:
    """The braced block beginning at `start`, honouring nesting."""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
        i += 1
    return ""


def _declarations(name: str, script: str, directory: Path) -> list[tuple[str, str]]:
    """Every place `name` could be declared, as (text, source-label) pairs."""
    texts = [script]
    for candidate in (directory / "types.ts", directory.parent / "types.ts"):
        if candidate.exists():
            texts.append(LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", candidate.read_text())))
    return texts


def _resolve_named_type(name: str, script: str, directory: Path, seen=None) -> dict[str, bool]:
    """Resolve a props/slots declaration by name.

    Three forms are in use across frappe-ui, and a reader that knows only the
    first quietly reports a component as having no props at all:

      * `interface Props { … }` / `type Props = A & { … }` — intersections are
        followed, so both halves are reported.
      * `const alertProps = { title: { type: String } }` — the runtime object
        form, passed as `defineProps(alertProps)`.

    Declarations are matched at the start of a line. Without that anchor the
    `type AlertSlots` inside `import { type AlertSlots } from './types'` matches
    first, and the resolver walks off into whatever follows the import.
    """
    seen = set() if seen is None else seen
    if name in seen:
        return {}
    seen.add(name)

    decl = re.compile(
        rf"^\s*(?:export\s+)?(?:declare\s+)?"
        rf"(?:(?:interface|type)\s+{re.escape(name)}\b([^{{;]*)"
        rf"|const\s+{re.escape(name)}\s*(=))",
        re.M,
    )

    for text in _declarations(name, script, directory):
        m = decl.search(text)
        if not m:
            continue
        found = {}
        for parent in re.findall(r"[A-Za-z_$][\w$]*", m.group(1) or ""):
            if parent not in {"extends", "type", "interface", "ExtractPublicPropTypes", "typeof"}:
                found |= _resolve_named_type(parent, script, directory, seen)
        brace = text.find("{", m.end() - 1)
        if brace != -1:
            members = _members(_balanced(text, brace))
            # A runtime props object is `title: { type: String, default: … }`.
            # Nothing there is a TypeScript optional marker, so requiredness
            # cannot be read off it — assume nothing is required.
            if re.search(r"^\s*(?:export\s+)?const\b", m.group(0)):
                members = {k: False for k in members}
            found |= members
        if found:
            return found
    return {}


def _models(script: str) -> set[str]:
    """Props declared through defineModel.

    `defineModel()` is `modelValue`; `defineModel('open')` is `open`, bound as
    `v-model:open`. SettingsDialog declares both its `open` and `tab` props this
    way, so a reader that only knows about `modelValue` concludes it takes
    neither.
    """
    names = set()
    for m in re.finditer(r"defineModel\s*(?:<[^(]*?>)?\s*\(", script):
        arg = script[m.end() : m.end() + 80].lstrip()
        quoted = re.match(r"""['"]([\w$]+)['"]""", arg)
        names.add(quoted.group(1) if quoted else "modelValue")
    return names


def component_api() -> dict[str, dict]:
    """{component: {"props", "required", "slots", "forwards"}}."""
    api = {}
    for path in UI_SRC.rglob("*.vue"):
        script = _script(path.read_text())
        props, slots = {}, {}

        # `<script setup>` macros, the runtime props object, and the options
        # API — Button is written the last way, and reporting it as having no
        # props at all would exempt the most-used component in the library.
        for patterns, target in (
            ((r"defineProps\s*<", r"defineProps\s*\(\s*([A-Za-z_$][\w$]*)\s*\)",
              r"^\s*props:\s*([A-Za-z_$][\w$]*)\s*,"), props),
            ((r"defineSlots\s*<", r"defineSlots\s*\(\s*([A-Za-z_$][\w$]*)\s*\)",
              r"^\s*slots:\s*Object as SlotsType<"), slots),
        ):
            generic, runtime, options = patterns

            m = re.search(generic, script)
            if m:
                after = script[m.end() :]
                if after.lstrip().startswith("{"):
                    target |= _members(_balanced(script, script.find("{", m.end())))
                else:
                    typename = re.match(r"\s*([A-Za-z_$][\w$]*)", after)
                    if typename:
                        target |= _resolve_named_type(typename.group(1), script, path.parent)
                continue

            m = re.search(runtime, script)
            if m:
                target |= _resolve_named_type(m.group(1), script, path.parent)
                continue

            m = re.search(options, script, re.M)
            if m:
                if m.groups():
                    target |= {k: False for k in _resolve_named_type(m.group(1), script, path.parent)}
                else:
                    target |= _members(_balanced(script, script.find("{", m.end())))

        # A v-model always has a value, so nothing declared this way is required.
        props |= {name: False for name in _models(script)}

        # Some components deliberately accept more than they declare: with
        # `inheritAttrs: false` and `useAttrs()` they forward the rest to an
        # inner control. FormControl says so outright — `options` for a select,
        # `min`/`max` for a date picker — so its real surface is open-ended and
        # unknown-prop checking would be wrong rather than strict.
        forwards = "useAttrs(" in script or "inheritAttrs: false" in script

        if props or slots or forwards:
            api[path.stem] = {
                "props": set(props),
                "required": {name for name, required in props.items() if required},
                "slots": set(slots),
                "forwards": forwards,
            }
    return api
