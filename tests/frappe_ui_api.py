"""Read frappe-ui's own prop and slot declarations.

Every UI bug this session was the same mistake: passing a component a prop or a
slot it does not declare. Vue does not complain — an unknown prop becomes a
fallthrough attribute on the root element, and an unknown slot is simply never
rendered — so the page loads, nothing throws, and the thing is missing.

Guessing an API is cheap and reading one is cheaper, so this reads them.
"""

import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Either app's node_modules would do — `test_shared_runtime_is_byte_identical`
# proves the two SPAs run the same barrel over the same version — so this reads
# the tenant app's, which is the one that survives OneAdmin becoming a Space.
UI_PKG = ROOT / "apps/oneapp/frontend/node_modules/frappe-ui"
UI_SRC = UI_PKG / "src"

# Whether the vendored library is actually here.
#
# Everything in this module reads frappe-ui's own source, so on a machine that
# has not run `npm install` there is nothing to read. That is the normal state
# of CI, which installs Python and nothing else — and these are guards against
# the *library* changing shape under us, which only happens when somebody bumps
# it, which they do locally.
#
# `_sources` already skips a root that does not exist, so `component_api()`
# quietly returns `{}` there. Quietly is the problem: the tests then failed on
# `KeyError: 'SidebarHeader'` and on "SettingsDialog was restructured", which
# reads as frappe-ui having changed rather than as nothing being installed. CI
# was red on every run for days because of it, and a permanently red CI is one
# nobody looks at.
INSTALLED = UI_SRC.exists()


def needs_frappe_ui():
    """A skip marker for a module that cannot say anything without the library."""
    import pytest

    return pytest.mark.skipif(
        not INSTALLED,
        reason=(
            "frappe-ui is not installed — run `npm install` in "
            "apps/oneapp/frontend to check our usage against it"
        ),
    )

# Where components actually live. `src/` is the stable library; `experimental/`
# is a sibling of it, published under its own entry point with no
# backward-compatibility promise — CodeEditor, CodePreview, the parked Calendar
# and TextEditor families.
#
# Reading only `src/` meant every experimental component was unchecked, which is
# exactly backwards: an unstable API is the one where a prop most needs
# verifying against the source rather than against memory. Anything imported
# from `frappe-ui/experimental` is now held to the same standard as the rest.
UI_ROOTS = (UI_SRC, UI_PKG / "experimental")


def _sources(suffix: str):
    """Every file of a kind, across the roots that hold components."""
    for root in UI_ROOTS:
        if root.exists():
            yield from root.rglob(suffix)

# Attributes that are never props, whatever the component: Vue's own
# directives, the handful of attributes Vue itself consumes, and the
# accessibility attributes — `role` belongs with `aria-*`, not with the props:
# it is how an icon-only element gets a name, and no component in the library
# declares it.
#
# Deliberately short. An earlier version also listed the common HTML attributes
# — `title`, `type`, `placeholder`, `disabled` — and that quietly disabled the
# checks for them: `title` is a real prop on Alert, Dialog, SidebarHeader and
# SettingsRow, so a missing one could never be reported. Passing a genuine DOM
# attribute to a component that does not declare it is itself worth knowing
# about, so the rest are checked like anything else.
NOT_PROPS = re.compile(
    r"^(v-if|v-else|v-else-if|v-for|v-show|v-html|v-text|v-pre|v-once|v-cloak"
    r"|v-slot|key|ref|class|style|is|slot|role|data-.*|aria-.*)$"
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


def _members(block: str) -> dict[str, tuple[bool, str]]:
    """{name: (required, declared type)} for a TypeScript object-type body.

    Nested object types are dropped first: `menuItems?: { label: string }[]`
    declares `menuItems`, not `label`.

    Parentheses count the same way, and for the same reason. A function-typed
    property whose parameters are on their own lines —

        validateFile?: (
          file: File,
        ) => FileUploaderValidationResult

    — puts `file: File,` at the start of a line, which reads exactly like a
    member declaration and has no `?` on it. FileUploader came back as having a
    required prop called `file`, and the guard then reported correct markup as
    missing it. A guard that argues for changing something that works is the
    one failure mode worse than missing a bug.
    """
    flat, depth = [], 0
    for char in block:
        if char in "{(":
            depth += 1
        elif char in "})":
            depth -= 1
        elif depth == 0:
            flat.append(char)
        elif char == "\n":
            flat.append(char)

    names = {}
    for line in "".join(flat).split("\n"):
        # Three forms, all legal and all used in frappe-ui:
        #   property   `default?: (props: P) => any`
        #   method     `default(props: P): unknown`
        #   quoted     `'item-prefix'?: (props: P) => any`
        # Reading only the first is how FileUploader's one slot came back as
        # "it has none", and a guard that reports a component has no slots
        # cannot fail on a wrong one. Reading only the first two hid every
        # hyphenated slot in the library — Combobox's `item-prefix` and
        # `group-label`, Sidebar's and Dialog's alike — which are exactly the
        # ones a template has to quote, so they are exactly the ones somebody
        # is most likely to misspell.
        m = re.match(
            r"""\s*(?:'([^']+)'|"([^"]+)"|([A-Za-z_$][\w$]*))\s*(\??)\s*[:(](.*)""",
            line,
        )
        if m:
            name = m.group(1) or m.group(2) or m.group(3)
            names[name] = (not m.group(4), m.group(5).strip().rstrip(","))
    return names


def _runtime_members(block: str) -> dict[str, tuple[bool, str]]:
    """{name: (False, type)} for a runtime props object.

    `theme: { type: String as PropType<StatusTheme>, default: 'gray' }` carries
    its real type inside `PropType<…>`. The TypeScript-body reader drops nested
    braces, so without this the whole runtime-object family — Alert, Button,
    SidebarCard — reports no closed value sets, and `theme="orange"` stays
    invisible on exactly the components most likely to be handed one.

    Nothing here is optional-marked, so requiredness is not inferred.
    """
    members, i, depth = {}, 0, 0
    name = None
    while i < len(block):
        char = block[i]
        if depth == 0:
            m = re.compile(r"([A-Za-z_$][\w$]*)\s*:").match(block, i)
            if m and not name:
                name, i = m.group(1), m.end()
                members.setdefault(name, (False, ""))
                continue
        if char == "{":
            if depth == 0 and name:
                body = _balanced(block, i)
                prop_type = re.search(r"PropType<\s*(.*?)\s*>", body, re.S)
                members[name] = (False, prop_type.group(1) if prop_type else "")
                i += len(body) + 2
                name = None
                continue
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0:
            name = None
        i += 1
    return members


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


def _read(path: Path) -> str:
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", path.read_text()))


# `import type { InputLabelingProps } from '../../composables/useInputLabeling'`
IMPORT = re.compile(
    r"^\s*import\s+(?:type\s+)?\{([^}]*)\}\s*from\s*['\"]([^'\"]+)['\"]", re.M
)


def _imported_from(name: str, text: str, directory: Path) -> Path | None:
    """Where a named type is imported from, if it is."""
    for names, source in IMPORT.findall(text):
        imported = {
            part.replace("type ", "").strip().split(" as ")[0].strip()
            for part in names.split(",")
        }
        if name not in imported or not source.startswith("."):
            continue
        base = (directory / source).resolve()
        for candidate in (base.with_suffix(".ts"), base / "index.ts", base.with_suffix(".d.ts")):
            if candidate.exists():
                return candidate
    return None


def _declarations(name: str, script: str, directory: Path) -> list[str]:
    """Every place `name` could be declared.

    The component's own script and the `types.ts` beside it cover most of
    frappe-ui — but not the props a component inherits. `SwitchProps extends
    InputLabelingProps`, and that interface lives in `composables/`, so a reader
    that stops at the directory reports Switch as taking no `label` and no
    `description`. It takes both, and the guard then flags correct markup as
    wrong, which is the one failure mode worse than missing a bug: it argues for
    removing something that works.

    So a named import is followed to the file it comes from.
    """
    texts = [script]
    for candidate in (directory / "types.ts", directory.parent / "types.ts"):
        if candidate.exists():
            texts.append(_read(candidate))

    for text in list(texts):
        source = _imported_from(name, text, directory)
        if source:
            texts.append(_read(source))
    return texts


def _resolve_named_type(name: str, script: str, directory: Path, seen=None) -> dict[str, tuple]:
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
                members = _runtime_members(_balanced(text, brace))
            found |= members
        if found:
            return found
    return {}


# A union made only of quoted string literals: 'gray' | 'blue' | 'red'.
QUOTED = re.compile(r"""'([^']*)'|"([^"]*)\"""")
LITERALS = re.compile(
    r"""^\s*\|?\s*(?:'[^']*'|"[^"]*")(?:\s*\|\s*(?:'[^']*'|"[^"]*"))*\s*$"""
)


def _quoted(text: str) -> set[str]:
    return {single or double for single, double in QUOTED.findall(text)}


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, set[str]]:
    """Every `type X = 'a' | 'b'` in the package: {name: {directory: values}}.

    Indexed package-wide because aliases are shared — `StatusTheme` lives in
    `components/shared/statusIcon.ts` and Alert, SidebarCard and Toast all use
    it, so looking only beside the component that uses one finds nothing.

    Kept per-directory because short names are reused: `Variant` is
    `solid|subtle|outline|ghost` in Button and `outline|subtle` in TimePicker.
    Resolution prefers the component's own directory and otherwise requires the
    name to be unambiguous, so a clash is never guessed at.
    """
    index = {}
    for path in _sources("*.ts"):
        text = LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", path.read_text()))
        # The body runs to the `;` or to the next top-level declaration:
        # DialogSize is fifteen values one per line, and a single-line read
        # leaves the most-used size union unchecked.
        for name, body in re.findall(
            r"^[ \t]*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*="
            r"((?:[^;]|\n)*?)(?=;|\n[ \t]*\n|\n[ \t]*(?:export|type|interface|const)\b|\Z)",
            text,
            re.M,
        ):
            if LITERALS.match(" ".join(body.split())):
                index.setdefault(name, {})[path.parent] = _quoted(body)
    return index


def literal_union(declared: str, script: str, directory: Path) -> set[str] | None:
    """The allowed values when a prop's type is a union of string literals.

    Returns None for every other type, so only genuinely closed sets are
    checked. A named alias is followed once: `theme?: StatusTheme` is as closed
    a set as `theme?: 'gray' | 'red'`, and Alert declares it the first way.
    """
    declared = declared.strip()
    if not declared:
        return None

    if LITERALS.match(declared):
        return _quoted(declared)

    if re.fullmatch(r"[A-Za-z_$][\w$]*", declared):
        by_directory = _alias_index().get(declared, {})
        if directory in by_directory:
            return by_directory[directory]
        unique = {frozenset(values) for values in by_directory.values()}
        if len(unique) == 1:
            return set(next(iter(unique)))
    return None


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
    for path in _sources("*.vue"):
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
                    target |= _resolve_named_type(m.group(1), script, path.parent)
                else:
                    target |= _members(_balanced(script, script.find("{", m.end())))

        # A v-model always has a value, so nothing declared this way is required.
        props |= {name: (False, "") for name in _models(script)}

        # Some components deliberately accept more than they declare: with
        # `inheritAttrs: false` and `useAttrs()` they forward the rest to an
        # inner control. FormControl says so outright — `options` for a select,
        # `min`/`max` for a date picker — so its real surface is open-ended and
        # unknown-prop checking would be wrong rather than strict.
        forwards = "useAttrs(" in script or "inheritAttrs: false" in script

        if props or slots or forwards:
            enums = {}
            for name, (_, declared) in props.items():
                values = literal_union(declared, script, path.parent)
                if values:
                    enums[name] = values

            api[path.stem] = {
                "props": set(props),
                "required": {n for n, (required, _) in props.items() if required},
                "enums": enums,
                "slots": set(slots),
                "forwards": forwards,
            }
    return api
