"""Options handed to useResource/useAction must be options useCall reads.

The same silence as the prop bugs, one layer down. `useCall` takes the extra
keys of its options object and ignores them: writing `enabled: false` — the name
the option has in TanStack Query and in frappe-ui's older helpers — gave a
resource that fetched immediately anyway, on a surface that was not allowed to
call the endpoint. The option is `immediate`. Nothing warned.
"""

import re
from pathlib import Path

import pytest

from frappe_ui_api import ROOT, UI_SRC, _balanced

APPS = ("oneapp", "oneapp_control")

# What our two wrappers consume themselves before handing the rest to useCall.
WRAPPER_OPTIONS = {
    "useResource": {"watch", "silent", "transform", "onError"},
    "useAction": {"successMessage", "silent", "transform", "onSuccess", "onError"},
}

CALL = re.compile(r"\b(useResource|useAction)\s*\(")


def use_call_options() -> set[str]:
    """The option names useCall declares, read from frappe-ui itself."""
    types = UI_SRC / "data-fetching/useCall/types.ts"
    assert types.exists(), f"{types} is missing — frappe-ui moved its data layer"
    body = types.read_text()
    brace = body.index("{", body.index("UseCallOptions"))
    return set(re.findall(r"^\s{2}([A-Za-z_$][\w$]*)\??:", _balanced(body, brace), re.M))


def options_literal(source: str, start: int) -> str | None:
    """The options object literal of a wrapper call, from just after its `(`."""
    depth, i = 0, start
    while i < len(source):
        char = source[i]
        if char == "{" and depth == 0:
            return _balanced(source, i)
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:  # the call's own closing paren: no options passed
                return None
            depth -= 1
        i += 1
    return None


def own_keys(literal: str) -> set[str]:
    """Top-level keys, with nested objects, arrays and calls dropped first."""
    flat, depth = [], 0
    for char in literal:
        if char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
        elif depth == 0 or char == "\n":
            flat.append(char)
    return set(re.findall(r"(?:^|,)\s*([A-Za-z_$][\w$]*)\s*:", "".join(flat)))


def sources(app: str):
    root = ROOT / f"apps/{app}/frontend/src"
    return {
        p.relative_to(root).as_posix(): p.read_text()
        for p in root.rglob("*")
        if p.suffix in (".vue", ".js")
    }


@pytest.mark.parametrize("app", APPS)
def test_no_unknown_call_options(app):
    allowed_base = use_call_options()
    problems = []
    for path, source in sources(app).items():
        for m in CALL.finditer(source):
            literal = options_literal(source, m.end())
            if literal is None:
                continue
            allowed = allowed_base | WRAPPER_OPTIONS[m.group(1)]
            unknown = own_keys(literal) - allowed
            if unknown:
                problems.append(
                    f"{app}/{path}: {m.group(1)}() was given {sorted(unknown)}, "
                    f"which useCall ignores — it reads {sorted(allowed)}"
                )
    assert not problems, "\n".join(problems)


def test_the_reader_found_the_data_layer():
    options = use_call_options()
    assert {"url", "immediate", "params", "transform"} <= options, sorted(options)
    assert "enabled" not in options, "frappe-ui gained `enabled`; relax this guard"
