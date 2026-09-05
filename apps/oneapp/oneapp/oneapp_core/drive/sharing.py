"""Giving a file to somebody: a colleague, or a stranger with a link.

Two mechanisms because they answer two questions, and neither substitutes for
the other. A colleague gets a `DocShare` — the same row the record surface
writes, read back by the same `get_list` every other reader here uses, revoked
by removing it. That is the whole of the in-workspace access model and there is
nothing of ours in it.

The rest of this file is the other one.

## A link that outlives a session

The one thing the framework genuinely does not have. `File.is_private` is a
site-wide flag with no expiry and no audit; a `DocShare` needs the other person
to have an account here. "Send this drawing to the consultant until Friday" is
neither, and it is the request people actually make.

So: a row naming one file, a secret that goes in the URL, and a date. Frappe
Drive calls the same idea a `Drive Token`, and it is the one part of Drive's
access model worth taking — because it is the part that answers a question
`DocShare` cannot.

Three things this refuses, each because the alternative is a file published for
ever by somebody who has since left:

  * **no expiry** — a link with no end is exactly that;
  * **a folder** — a link to a folder is a link to everything anybody puts in
    it afterwards, which is not what the person sharing agreed to;
  * **a secret that could be guessed** — 32 bytes from `secrets`, not a uuid4
    and not a hash of anything about the file.
"""

import secrets

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, now_datetime

# How long a link may last. Not a technical bound — a link somebody made for a
# consultant in March is a file that consultant still has in December, and the
# person who made it will not remember it exists.
MAX_DAYS = 90
DEFAULT_DAYS = 7

# Bytes of randomness in the URL. `token_urlsafe(32)` is 43 characters, which
# is unguessable and still short enough to paste into an email.
SECRET_BYTES = 32


# --------------------------------------------------------------------------- #
# A colleague
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def people(file: str) -> dict:
    """Who this file has been given to, and how far."""
    doc = frappe.get_doc("File", file)
    doc.check_permission("read")

    from oneapp.oneapp_core import collab

    return {
        **collab.shares_of("File", file),
        # Asked rather than assumed, so the control that is drawn and the write
        # that is allowed read the same flag at the same moment.
        "can_share": bool(frappe.has_permission("File", "share", doc=doc)),
    }


@frappe.whitelist(methods=["GET"])
def colleagues(query: str = "") -> list[dict]:
    """Who a file can be shared with.

    The same people the assignment picker offers, asked without a screen: a
    file is not on a space, so there is no screen to bound it by. What bounds
    it instead is the only definition of "colleague" this site has — an enabled
    account holding a role this app granted.
    """
    from oneapp.oneapp_core.spaceview.assign import ASSIGNEE_PAGE, _colleagues

    found = frappe.get_all(
        "User",
        filters={"enabled": 1, "name": ["in", _colleagues()]},
        or_filters=(
            {"full_name": ["like", f"%{query}%"], "name": ["like", f"%{query}%"]}
            if query else None
        ),
        fields=["name", "full_name", "user_image"],
        limit_page_length=ASSIGNEE_PAGE,
        order_by="full_name asc",
    )
    return [
        {"value": row["name"], "label": row["full_name"] or row["name"],
         "image": row["user_image"]}
        for row in found
    ]


@frappe.whitelist(methods=["POST"])
def share_with(file: str, user: str | None = None, everyone: str | int = 0,
               level: str = "read") -> dict:
    """Give it to a colleague, or change how far their share goes.

    Bounded to the workspace by the same list the assignment picker offers. A
    share with an account that holds no role on any space this workspace was
    granted is a hole rather than a feature — and on `File` it is a worse one
    than on a record, because a file is the thing people actually send.
    """
    doc = frappe.get_doc("File", file)
    doc.check_permission("share")

    from oneapp.oneapp_core import collab
    from oneapp.oneapp_core.spaceview.assign import _colleagues

    if user and user not in _colleagues():
        frappe.throw(_("{0} is not on this workspace.").format(user))

    return {
        **collab.share("File", file, user=user, everyone=everyone, level=level),
        "can_share": True,
    }


@frappe.whitelist(methods=["POST"])
def unshare_with(file: str, user: str | None = None,
                 everyone: str | int = 0) -> dict:
    """Take a colleague's share back."""
    doc = frappe.get_doc("File", file)
    doc.check_permission("share")

    from oneapp.oneapp_core import collab

    return {
        **collab.unshare("File", file, user=user, everyone=everyone),
        "can_share": True,
    }


# --------------------------------------------------------------------------- #
# A stranger
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def make_link(file: str, days: int = DEFAULT_DAYS, label: str = "") -> dict:
    """Hand one file to somebody who has no account here."""
    doc = frappe.get_doc("File", file)
    # `share`, not `read`. Being able to open a file and being able to publish
    # it to the internet are different permissions and Frappe already has both.
    if not frappe.has_permission("File", "share", doc=doc):
        frappe.throw(_("You cannot share that file."), frappe.PermissionError)

    if doc.is_folder:
        frappe.throw(_("A folder cannot be shared as a link — "
                       "it would include whatever is put in it later."))

    days = int(days or DEFAULT_DAYS)
    if not 1 <= days <= MAX_DAYS:
        frappe.throw(_("A link can last between 1 and {0} days.").format(MAX_DAYS))

    link = frappe.get_doc({
        "doctype": "File Link",
        "file": file,
        "label": label or doc.file_name,
        "secret": secrets.token_urlsafe(SECRET_BYTES),
        "expires_on": add_days(now_datetime(), days),
    }).insert(ignore_permissions=True)

    return _shape(link)


@frappe.whitelist(methods=["GET"])
def links(file: str) -> list[dict]:
    """Every link on one file, so a person can see what they have given away."""
    doc = frappe.get_doc("File", file)
    if not frappe.has_permission("File", "share", doc=doc):
        frappe.throw(_("You cannot see that file's links."), frappe.PermissionError)

    return [
        _shape(frappe.get_doc("File Link", name))
        for name in frappe.get_all(
            "File Link", filters={"file": file}, pluck="name",
            order_by="creation desc",
        )
    ]


@frappe.whitelist(methods=["POST"])
def revoke(name: str) -> dict:
    """Take a link back early.

    Marked rather than deleted: "who shared this, and when did it stop" is a
    question somebody will ask after something has gone wrong, and a deleted
    row answers it with silence.
    """
    link = frappe.get_doc("File Link", name)
    if not frappe.has_permission("File", "share", doc=frappe.get_doc("File", link.file)):
        frappe.throw(_("That is not yours to revoke."), frappe.PermissionError)

    link.db_set("revoked", 1, update_modified=False)
    return {"ok": True, "revoked": name}


def _shape(link) -> dict:
    return {
        "name": link.name,
        "label": link.label,
        "url": f"/api/method/oneapp.oneapp_core.drive.open_link?secret={link.secret}",
        "expires_on": str(link.expires_on) if link.expires_on else "",
        "revoked": bool(link.revoked),
        "opened": link.opened or 0,
        "last_opened": str(link.last_opened) if link.last_opened else "",
    }


@frappe.whitelist(allow_guest=True, methods=["GET"])
def open_link(secret: str):
    """Follow a link. No session, by design.

    Guest-callable, so the secret is the whole of the authentication — which is
    why it is 32 random bytes and why every refusal below says the same thing.
    A link that told a stranger *why* it failed would tell them whether the
    secret was right.
    """
    name = frappe.db.get_value("File Link", {"secret": secret}, "name") if secret else None
    link = frappe.get_doc("File Link", name) if name else None

    if not link or link.revoked or not link.expires_on:
        frappe.throw(_("This link is not available."), frappe.PermissionError)
    if get_datetime(link.expires_on) < now_datetime():
        frappe.throw(_("This link is not available."), frappe.PermissionError)

    link.db_set("opened", (link.opened or 0) + 1, update_modified=False)
    link.db_set("last_opened", now_datetime(), update_modified=False)
    # Kept, which takes saying so: Frappe commits a request only when its HTTP
    # method changes server state, and this one is a `GET` because following a
    # link is. Without this the count and the date are rolled back at the end of
    # every request — and the count *is* the audit trail this row exists for.
    frappe.local.flags.commit = True

    # Not `r2.download`: that route checks whether *the reader* may read the
    # file, and the reader here is a guest with no account. The secret was the
    # check, and it already passed.
    from oneapp.oneapp_core.storage import r2

    r2.serve(frappe.get_doc("File", link.file))


def sweep_links():
    """Drop links that expired more than a month ago. A scheduled job.

    Not the moment they expire: the row is the audit trail, and "this stopped
    working last Tuesday" is the answer somebody needs in the week after it
    stops working.
    """
    cutoff = add_days(now_datetime(), -30)
    stale = frappe.get_all(
        "File Link",
        filters={"expires_on": ["<", cutoff]},
        pluck="name",
        limit_page_length=200,
    )
    for name in stale:
        frappe.delete_doc("File Link", name, ignore_permissions=True)
    return len(stale)
