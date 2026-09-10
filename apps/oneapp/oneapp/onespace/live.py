"""Who may be in a room, and who they are once they are in it.

The rest of live editing is in two places that are not Python:
`apps/oneapp/realtime/handlers.js`, which runs inside the socketio process the
bench already runs and relays messages between browsers, and the collaboration
modules in the SPA. This file is the one question the relay asks the framework,
once per room per socket, and it exists because the relay must not be the thing
that decides who may read a file.

It is deliberately small and deliberately not chatty. A Yjs update per
keystroke through a whitelisted method is what Frappe Sheets does — and what
made their own bench answer `ERR_INSUFFICIENT_RESOURCES` after five and a half
thousand POSTs during one paste. Every message after `admit` goes browser →
node → browsers and never reaches a Python worker.

## What a kind is

A client names a *kind* and a *record*, never a room. `admit` maps the pair to
a room name and hands that back; the relay joins the room it was told, not the
one it was asked for. Without that this would be an open pub/sub bus over every
row on the site, joinable by anyone with a socket.

There is one kind, `file`, and both editors use it: a sheet and a document are
both `File` rows, which is the decision `docs/WRITER.md` §1 and `docs/SHEETS.md`
Stage 1 already made and the reason sharing, folders and the bin came free.
"""

import frappe

# The cursor palette. Eight hues that stay apart on both grounds and are not
# any of the status colours — a peer's cursor must never read as an error.
# Frappe Sheets picks from a list of the same size for the same reason; these
# are ours, because theirs are Google's and clash with our accent.
COLOURS = (
    "#2563eb", "#db2777", "#16a34a", "#d97706",
    "#7c3aed", "#0891b2", "#ea580c", "#4f46e5",
)


def colour_for(user: str) -> str:
    """The same person is the same colour in every room, on every browser.

    Hashed rather than assigned, so two people in a room cannot be handed the
    same seat by two different sockets racing — and so a peer who reconnects
    does not change colour under everybody's cursor.
    """
    total = 0
    for char in user or "":
        total = (total * 31 + ord(char)) & 0xFFFFFFFF
    return COLOURS[total % len(COLOURS)]


def initials_for(full_name: str, user: str) -> str:
    words = [word for word in (full_name or "").split() if word]
    if not words:
        return (user or "?")[:1].upper()
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][:1] + words[-1][:1]).upper()


@frappe.whitelist(methods=["GET"])
def admit(kind: str, name: str) -> dict:
    """May this person be in this room, and may they write in it?

    Called by the socket relay over the loopback with the caller's own session,
    so the permission check below is the caller's own. Never called from the
    browser — the browser has no use for the answer, and letting it ask would
    invite it to believe its own reply about whether it may write.

    A refusal is a plain `{"ok": False}` and says nothing else, for the same
    reason `open_link` does: a refusal that explains itself is a probe that
    works.
    """
    if kind != "file" or not name:
        return {"ok": False}

    if not frappe.db.exists("File", name):
        return {"ok": False}

    doc = frappe.get_doc("File", name)
    if not frappe.has_permission("File", "read", doc=doc):
        return {"ok": False}

    user = frappe.session.user
    if user == "Guest":
        return {"ok": False}

    full_name = frappe.db.get_value("User", user, "full_name") or user
    image = frappe.db.get_value("User", user, "user_image") or ""

    return {
        "ok": True,
        "name": doc.name,
        "write": bool(frappe.has_permission("File", "write", doc=doc)),
        "who": {
            "user": user,
            "full_name": full_name,
            "initials": initials_for(full_name, user),
            "image": image,
            "colour": colour_for(user),
        },
    }


@frappe.whitelist(methods=["GET"])
def presence(kind: str, name: str) -> dict:
    """Whether live editing is available at all, asked by the editor on open.

    Not the roster — the roster comes over the socket, and asking the framework
    for it would be a second answer that can disagree with the first. This says
    only what the browser cannot work out for itself: that it is signed in, and
    that this file is one it may write.
    """
    seat = admit(kind, name)
    if not seat.get("ok"):
        return {"live": False}
    return {"live": True, "write": seat["write"], "who": seat["who"]}
