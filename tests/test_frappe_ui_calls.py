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


def test_reads_go_to_the_v2_method_endpoint():
    """useCall reads its payload as `data.value?.data` — the API v2 envelope.

    `/api/method/…` is v1 and answers `{message: …}`, so that lookup finds
    nothing and the resource settles with `data === null` after a request that
    succeeded. Nothing throws and nothing logs: the customer portal sat on its
    loading spinner, and the user menu showed "Account" instead of a name.

    Checked against frappe-ui's own source rather than pinned, so the day it
    learns to read `message` this fails and the prefix can go back.
    """
    resource = (ROOT / "apps/oneapp_control/frontend/src/lib/resource.js").read_text()
    assert "/api/v2/method/" in resource, "reads are pointed at the v1 endpoint again"

    use_call = (UI_SRC / "data-fetching/useCall/useCall.ts").read_text()
    assert "data.value?.data" in use_call, (
        "useCall no longer reads the v2 envelope — check whether the v2 prefix "
        "in methodUrl() is still right"
    )


def test_the_two_apps_read_through_the_same_endpoint():
    versions = {
        app: "/api/v2/method/" in (ROOT / f"apps/{app}/frontend/src/lib/resource.js").read_text()
        for app in APPS
    }
    assert all(versions.values()), f"one app is still on v1: {versions}"


# --------------------------------------------------------------------------- #
# The v1 data layer, and only it
#
# frappe-ui's v0 helpers — createResource, createListResource,
# createDocumentResource, and the `Resource` / `List Resource` /
# `Document Resource` documentation calls them — are replaced in v1 by useCall,
# useList, useDoc, useDoctype and useNewDoc. The v0 names still resolve on the
# v1 line for a while, which is exactly what makes this worth pinning: code
# written against them keeps working until it does not, and by then it is
# everywhere.
#
# We wrap four of the five. useNewDoc is deliberately absent: a new record is
# created through `spaceview.save`, which is bounded by the screen's own field
# list, and a client-side document that inserts whatever it holds would be a way
# around that bound rather than a convenience.
# --------------------------------------------------------------------------- #

RETIRED = (
    "createResource",
    "createListResource",
    "createDocumentResource",
    "createDocumentSubmitResource",
)

V1 = ("useCall", "useList", "useDoc", "useDoctype")


@pytest.mark.parametrize("app", APPS)
def test_no_v0_data_helpers(app):
    root = ROOT / f"apps/{app}/frontend/src"
    offenders = []
    for path in sorted(list(root.rglob("*.js")) + list(root.rglob("*.vue"))):
        source = path.read_text()
        for name in RETIRED:
            if re.search(rf"\b{name}\b", source):
                offenders.append(f"{path.relative_to(root)}: {name}")
    assert not offenders, (
        "these are the v0 data layer; use useCall / useList / useDoc / useDoctype "
        "through '@/lib/resource': " + ", ".join(offenders)
    )


@pytest.mark.parametrize("app", APPS)
def test_the_wrappers_are_built_on_the_v1_layer(app):
    """And that the names are still what frappe-ui exports, so a rename shows up
    here rather than as a page that fetches nothing."""
    source = (ROOT / f"apps/{app}/frontend/src/lib/resource.js").read_text()
    for name in V1:
        assert re.search(rf"\b{name}\b", source), f"{app} no longer uses {name}"

    # The data layer is its own barrel; the package root re-exports it.
    index = UI_SRC / "data-fetching/index.ts"
    if not index.exists():
        pytest.skip("frappe-ui is not installed")
    exported = index.read_text()
    for name in V1 + ("useNewDoc",):
        assert name in exported, f"frappe-ui no longer exports {name}"
