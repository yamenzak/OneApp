"""Every method the SPAs call must exist, be whitelisted, and accept the verb.

Three separate silences, all producing a page that loads and shows nothing:

* A method name that does not resolve is a 404 — except our SPA route rules
  answer any unmatched path with the app's own HTML at 200, so the fetch fails
  parsing JSON rather than erroring usefully.
* A method whitelisted `methods=["GET"]` and called with POST is rejected as a
  PermissionError, which reads like an auth problem rather than a verb problem.
  That is what made the signup page report itself closed: `signup_open` is
  GET-only and `callMethod` posts.
* A guest surface calling a method without `allow_guest` fails only for the
  people it was built for, and never for whoever is testing it while logged in.

The verb each helper uses is fixed: `useResource` is useCall's default GET,
`useAction` sets POST, and `callMethod` goes through frappe-ui's `call()`, which
is POST-only.
"""

import re
from pathlib import Path

import pytest

from frappe_ui_api import ROOT

APPS = ("oneapp", "oneapp_control")
HELPER_VERB = {"useResource": "GET", "useAction": "POST", "callMethod": "POST"}

# Frappe's own endpoints, whitelisted in the framework rather than in our apps.
FRAMEWORK = {
    "frappe.client.get": {"GET", "POST"},
    "frappe.client.get_list": {"GET", "POST"},
    "frappe.client.get_value": {"GET", "POST"},
    "frappe.client.set_value": {"POST"},
    "frappe.client.insert": {"POST"},
    "frappe.client.delete": {"POST"},
    "frappe.auth.get_logged_user": {"GET", "POST"},
}

CALL = re.compile(
    r"\b(?P<helper>useResource|useAction|callMethod)\(\s*"
    r"(?:[`'\"](?P<literal>[\w.]+)[`'\"]|method\(\s*'(?P<via>[\w.]+)'\s*\))"
    # An explicit `method: 'GET'` in the options overrides the helper's default.
    r"(?P<rest>(?:[^()]|\([^()]*\))*\))?"
)
EXPLICIT_VERB = re.compile(r"\bmethod:\s*'(\w+)'")
# `const method = (name) => \`oneapp_control.api.signup.${name}\``
PREFIX = re.compile(r"const method = \(name\) => [`'\"]([\w.]*)\$\{name\}[`'\"]")


def whitelisted() -> dict[str, dict]:
    """{dotted path: {"verbs": {...}, "guest": bool}} for our own apps."""
    found = {}
    for path in (ROOT / "apps").rglob("*.py"):
        source = path.read_text()
        for m in re.finditer(r"@frappe\.whitelist\(([^)]*)\)\s*\ndef (\w+)", source):
            args, name = m.groups()
            verbs = re.search(r"methods=\[([^\]]*)\]", args)
            module = path.as_posix().split("apps/", 1)[1].split("/", 1)[1]
            dotted = module[:-3].replace("/", ".")
            found[f"{dotted}.{name}"] = {
                "verbs": set(re.findall(r"\w+", verbs.group(1))) if verbs else {"GET", "POST"},
                "guest": "allow_guest=True" in args,
            }
    return found


def call_sites(app: str):
    """Yield (file, verb, dotted method) for every call the SPA makes."""
    root = ROOT / f"apps/{app}/frontend/src"
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".vue", ".js"):
            continue
        source = path.read_text()
        prefix = PREFIX.search(source)
        for m in CALL.finditer(source):
            if m.group("literal"):
                method = m.group("literal")
            elif prefix:
                method = prefix.group(1) + m.group("via")
            else:
                continue
            verb = EXPLICIT_VERB.search(m.group("rest") or "")
            yield (
                path.relative_to(root).as_posix(),
                verb.group(1) if verb else HELPER_VERB[m.group("helper")],
                method,
            )


def test_the_reader_found_the_call_sites():
    # A regex that matches nothing makes every assertion below vacuous.
    calls = [c for app in APPS for c in call_sites(app)]
    assert len(calls) > 25, f"only found {len(calls)} call sites"
    assert any(m.startswith("oneapp_control.api.signup.") for _, _, m in calls)
    assert any(m.startswith("oneapp_control.api.customer.") for _, _, m in calls)


def test_the_reader_found_the_whitelist():
    api = whitelisted()
    assert len(api) > 40, f"only found {len(api)} whitelisted methods"
    assert api["oneapp_control.api.signup.signup_open"]["guest"] is True


@pytest.mark.parametrize("app", APPS)
def test_called_methods_exist(app):
    api = whitelisted()
    missing = [
        f"{app}/{path}: {method} is not whitelisted anywhere"
        for path, _, method in call_sites(app)
        if method not in api and method not in FRAMEWORK
    ]
    assert not missing, "\n".join(missing)


@pytest.mark.parametrize("app", APPS)
def test_called_methods_accept_the_verb(app):
    api = whitelisted()
    problems = []
    for path, verb, method in call_sites(app):
        allowed = api.get(method, {}).get("verbs") or FRAMEWORK.get(method)
        if not allowed:
            continue
        if verb not in allowed:
            problems.append(
                f"{app}/{path}: sends {verb} to {method}, which is "
                f"whitelisted for {sorted(allowed)}"
            )
    assert not problems, "\n".join(problems)


def test_guest_surfaces_only_call_guest_methods():
    """Signup runs before anyone has an account."""
    api = whitelisted()
    problems = []
    for path, _, method in call_sites("oneapp_control"):
        if not path.startswith("pages/signup/"):
            continue
        entry = api.get(method)
        if entry and not entry["guest"]:
            problems.append(f"{path}: {method} is not allow_guest")
    assert not problems, "\n".join(problems)


# The document layer's own methods. Anything here reached through
# `frappe.client.*` is a hand-rolled version of something the library ships.
CLIENT_METHODS = re.compile(r"frappe\.client\.(get_list|get|set_value|insert|delete)\b")

# Where the wrappers themselves live. They are the one place allowed to know
# about the transport.
DATA_LAYER = ("lib/resource.js", "lib/api.js")


@pytest.mark.parametrize("app", APPS)
def test_documents_go_through_the_document_layer(app):
    """`useList` / `useDoc` / `useDoctype` are the recommended layer.

    They share one document store, so a row updated through a list and the same
    record open on a detail page stay in step, and each write submits
    independently. `frappe.client.get_list` through a generic call gives up all
    of that — and the helper we wrote on top of it was even called `useList`,
    shadowing the library's own.

    `lib/user.js` is the exception the User doctype forces: there is no
    `/api/v2/document/User/<me>` for the session user without knowing the name
    first, so it reads through the boot payload's user instead.
    """
    root = ROOT / f"apps/{app}/frontend/src"
    problems = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".vue", ".js"):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in DATA_LAYER or rel == "lib/user.js":
            continue
        for method in set(CLIENT_METHODS.findall(path.read_text())):
            problems.append(
                f"{app}/{rel}: frappe.client.{method} — use useDocList / "
                f"useDocument / useDocWrites from lib/resource"
            )
    assert not problems, "\n".join(problems)


def test_the_document_layer_wraps_the_recommended_composables():
    """And is the only place that imports them."""
    resource = (ROOT / "apps/oneapp/frontend/src/lib/resource.js").read_text()
    for composable in ("useList", "useDoc", "useDoctype"):
        assert f"  {composable},\n" in resource, f"{composable} is not wrapped"
    for wrapper in ("useDocList", "useDocument", "useDocWrites"):
        assert f"export function {wrapper}" in resource, f"{wrapper} is missing"
