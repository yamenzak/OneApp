"""Who has agreed to what, and who may not carry on until they do.

Two parties, because two different things are being agreed to and only one of
them can be agreed to by somebody else.

* **The workspace.** The Terms of Service, the Data Processing Addendum, the
  Subprocessors list and the AI Addendum are a contract with the organisation.
  The person who creates the workspace accepts them, and that binds everybody in
  it. One acceptance covers the workspace.
* **The person.** The Privacy Policy and the Cookie Policy describe the handling
  of *their* personal data, and an employer cannot agree to that on their
  behalf. Every person who signs in accepts those for themselves, once, and
  again whenever the version changes.

The Acceptable Use Policy is both: the organisation promises it and each person
acknowledges it, because it is the one document that describes what an
individual may not do.

What is recorded is not "yes": it is the document, the exact version, the text
that version hashed to, the account, the time, and the address it came from.
`Legal Document Version` keeps the rendered text of every version anybody has
ever agreed to, so the question "what did I agree to in March" has an answer.
"""

import frappe
from frappe import _

from . import assemble
from .documents import DOCUMENTS

WORKSPACE = "Workspace"
USER = "User"

#: Who has to accept what. `both` lands in each list, for the reason above.
AUDIENCE = {"customer": (WORKSPACE,), "user": (USER,), "both": (WORKSPACE, USER)}


def keys_for(party: str) -> list[str]:
    """The documents one party must accept, in the order they are shown."""
    return [
        key for key, one in DOCUMENTS.items()
        if one["audience"] and party in AUDIENCE[one["audience"]]
    ]


def _may_bind() -> bool:
    """Whether this person can accept on the workspace's behalf.

    The workspace owner, or our support account acting for them. Deliberately
    not "anybody who can read the settings screen": binding the organisation to
    a contract is the one thing that should not be delegated by accident.
    """
    from ..onespace.workspace import OWNER_ROLE, SUPPORT_ROLE

    return bool(set(frappe.get_roles()) & {OWNER_ROLE, SUPPORT_ROLE})


def _accepted(key: str, party: str, user: str | None = None) -> str | None:
    """The version of `key` this party last accepted, if any."""
    filters = {"document": key, "party": party}
    if party == USER:
        filters["user"] = user or frappe.session.user
    rows = frappe.get_all(
        "Legal Acceptance", filters=filters, fields=["version"],
        order_by="creation desc", limit=1, ignore_permissions=True,
    )
    return rows[0]["version"] if rows else None


def standing(user: str | None = None) -> list[dict]:
    """Every document that needs agreeing, and where this person stands on it."""
    user = user or frappe.session.user
    binds = _may_bind()
    rows = []

    for key, one in DOCUMENTS.items():
        if not one["audience"]:
            continue
        version = assemble.version_of(key)
        for party in AUDIENCE[one["audience"]]:
            if party == WORKSPACE and not binds:
                # Somebody else's to accept. It still blocks the workspace, but
                # not this person — telling them to accept a contract they
                # cannot bind is telling them to do the impossible.
                continue
            was = _accepted(key, party, user)
            rows.append({
                "document": key,
                "title": one["title"],
                "summary": one["summary"],
                "party": party,
                "version": version,
                "accepted": was == version,
                "previously": was,
            })
    return rows


@frappe.whitelist(methods=["GET"])
def outstanding() -> dict:
    """What this person has to agree to before carrying on.

    `blocking` is what they can do something about. `waiting` is what the
    workspace still owes and they cannot sign — an invited user cannot accept
    the Terms of Service, and should be told that rather than shown a button
    that will not work.
    """
    rows = standing()
    blocking = [one for one in rows if not one["accepted"]]
    waiting = []

    if not _may_bind():
        for key in keys_for(WORKSPACE):
            if not _accepted(key, WORKSPACE):
                waiting.append({"document": key, "title": DOCUMENTS[key]["title"]})

    return {
        "blocking": blocking,
        "waiting": waiting,
        "may_bind": _may_bind(),
        "ok": not blocking and not waiting,
    }


def _agent() -> str:
    """The browser that accepted, when there is one.

    `frappe.get_request_header` reaches for a request object that is not bound
    outside one, and raises rather than returning nothing. Accepting is not
    only something a browser does — the dev fixture agrees on behalf of both
    its users, and a console or a migration may too — so the absence of a
    request is a blank field, not a failure.
    """
    if not getattr(frappe.local, "request", None):
        return ""
    return (frappe.get_request_header("User-Agent") or "")[:500]


def record(key: str, party: str, user: str | None = None) -> dict:
    """Write one acceptance, and the version's text if it is new here.

    `ignore_permissions` because accepting is the one write a person makes
    before they have been let in, and the row is about them.
    """
    if key not in DOCUMENTS or not DOCUMENTS[key]["audience"]:
        frappe.throw(_("There is no such document to agree to."))
    if party not in (WORKSPACE, USER):
        frappe.throw(_("There is no such party."))
    if party == WORKSPACE and not _may_bind():
        frappe.throw(
            _("Only the workspace owner can agree to this on the organisation's "
              "behalf."),
            frappe.PermissionError,
        )

    rendered = assemble.render(key)
    version = rendered["version"]
    stored = f"{key}-{version}"

    if not frappe.db.exists("Legal Document Version", stored):
        frappe.get_doc({
            "doctype": "Legal Document Version",
            "document": key,
            "title": rendered["title"],
            "version": version,
            "revision": rendered["revision"],
            "audience": rendered["audience"],
            "html": rendered["html"],
            "text": assemble.text_of(key),
        }).insert(ignore_permissions=True)

    row = frappe.get_doc({
        "doctype": "Legal Acceptance",
        "document": key,
        "version": version,
        "stored_version": stored,
        "party": party,
        "user": user or frappe.session.user,
        "accepted_on": frappe.utils.now_datetime(),
        "address": (getattr(frappe.local, "request_ip", None) or "")[:140],
        "agent": _agent(),
    }).insert(ignore_permissions=True)

    return {"document": key, "party": party, "version": version, "name": row.name}


@frappe.whitelist(methods=["POST"])
def accept(documents: str | list) -> dict:
    """Agree to a list of documents, as whichever party each one needs.

    The client sends what it was shown. Anything already accepted at this
    version is skipped rather than refused, because two tabs open at the same
    dialog is a thing that happens.
    """
    wanted = frappe.parse_json(documents) if isinstance(documents, str) else documents
    if not isinstance(wanted, list):
        frappe.throw(_("Send the list of documents you are agreeing to."))

    done = []
    for key in wanted:
        one = DOCUMENTS.get(key)
        if not one or not one["audience"]:
            continue
        for party in AUDIENCE[one["audience"]]:
            if party == WORKSPACE and not _may_bind():
                continue
            if _accepted(key, party) == assemble.version_of(key):
                continue
            done.append(record(key, party))

    return {"accepted": done, **outstanding()}


def require(where: str = "") -> None:
    """Refuse to go on while something is outstanding.

    Called from the paths where carrying on would be carrying on *under* an
    agreement nobody has made: creating a workspace, enabling a space. Not from
    every request — the shell asks once when it boots and puts the dialog up,
    and a check on every read would be a check on every read.
    """
    answer = outstanding()
    if answer["ok"]:
        return
    said = _("This workspace has agreements outstanding. Open them from Settings, agree, and try again.")
    frappe.throw(said + (f" ({where})" if where else ""), frappe.PermissionError)
