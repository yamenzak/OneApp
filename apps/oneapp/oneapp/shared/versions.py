"""Earlier drafts of a file's body — for a workbook and for a document alike.

Derived from frappe/sheets (`sheets/versioning/`, AGPL-3.0, © Frappe
Technologies Pvt. Ltd. and contributors). Both projects are AGPL-3.0 and this
file stays that way.

What was taken is the policy, which is the part that took them work to get
right: snapshot the first time a file is saved so the panel is never empty,
then on every Nth save or after T seconds of work, so a burst of autosaves is
one version and an afternoon of editing is a readable list. Named versions are
always kept. Automatic ones are thinned on a tiered schedule, so a file edited
every day for a year costs a bounded number of blobs rather than an unbounded
one.

What was not taken is their op log. Theirs exists because their save is a diff
against a sequence; ours is total — the browser holds the whole body and hands
the whole body back — so a version *is* a snapshot and there is nothing to
replay. That also removes their `state_at`: reading a version is reading its
payload.

One module for all three kinds because there is only one shape here. A version
is a blob, a file, a moment, a person and a name; whether the blob is
`codec.py`'s gzipped workbook, a document's ProseMirror JSON or the bytes of a
`.py` is the store's business, and restoring is handing it back to the store it
came from.
"""

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

SHEET = "Sheet"
DOC = "Doc"
#: Every file whose bytes are its own — a `.py`, a `.md`, a `.txt`. One kind
#: rather than one per language: the store is the object either way, and what
#: distinguishes a Python file from a README is what opens it, not where it
#: lives.
TEXT = "Text"
KINDS = (SHEET, DOC, TEXT)

#: Snapshot after this many saves, or after this many seconds of editing —
#: whichever comes first. Frappe's numbers, which are Google Sheets' numbers,
#: and the reason to keep them is that they were tuned against real editing
#: rather than guessed.
EVERY_SAVES = 25
EVERY_SECONDS = 30

#: How dense the automatic versions stay as they age: (older than N hours,
#: keep one per M hours). Past the last tier nothing automatic survives, which
#: is what stops a year of editing being a year of blobs. Named versions are
#: never in this list's reach.
TIERS = (
    (24, 0),
    (24 * 7, 1),
    (24 * 30, 24),
    (24 * 90, 168),
)
FORGET_AFTER_HOURS = 24 * 90

TITLE_MAX = 140


def _store(kind: str):
    """The module that owns bodies of this kind.

    Imported by absolute path and not relatively. `shared` sits beside the
    product modules rather than above them, so `.sheets` reaches for a sibling
    of `shared` that has never existed — and it resolves at *call* time, which
    is why a wrong one here is not an import error at boot but a save that
    fails in a browser.
    """
    if kind == SHEET:
        from oneapp.onesheet import book

        return book
    if kind == DOC:
        from oneapp.onedoc import body

        return body
    if kind == TEXT:
        from oneapp.onedoc import text

        return text
    frappe.throw(_("There is no such thing as a {0} version.").format(kind))


def _body(kind: str, file: str) -> dict:
    """The current payload and save count of one file's body."""
    return _store(kind).head_of(file)


# --------------------------------------------------------------------------- #
# Taking one
# --------------------------------------------------------------------------- #

def keep(file: str, kind: str, title: str = "", manual: bool = False) -> str | None:
    """Write a version of this file's body as it stands. The row's name, or None.

    `None` means the policy said no, which is the ordinary answer during a
    burst of autosaves. Callers save first and offer a version afterwards; a
    refused version is never an error.
    """
    head = _body(kind, file)
    seq = cint(head.get("head_seq"))
    last = latest(file)

    if not manual and not _due(seq, last):
        return None

    payload = head.get("payload") or ""
    row = frappe.get_doc({
        "doctype": "File Version",
        "file": file,
        "kind": kind,
        "title": (title or "").strip()[:TITLE_MAX] or _stamp(),
        "manual": 1 if manual else 0,
        "payload": payload,
        "byte_size": len(payload.encode("utf-8")),
        "at_seq": seq,
        "saves": max(0, seq - cint(last.get("at_seq") if last else 0)),
    }).insert(ignore_permissions=True)

    return row.name


def _due(seq: int, last: dict | None) -> bool:
    """Frappe's policy, unchanged: dense at first, then bursty-tolerant."""
    if seq <= 0:
        return False
    if last is None:
        return True
    since = seq - cint(last.get("at_seq"))
    if since <= 0:
        return False
    if since >= EVERY_SAVES:
        return True
    elapsed = (now_datetime() - get_datetime(last["creation"])).total_seconds()
    return elapsed >= EVERY_SECONDS


def _stamp() -> str:
    """What an unnamed version is called: when it was taken."""
    return frappe.utils.format_datetime(now_datetime(), "d MMM, HH:mm")


def latest(file: str) -> dict | None:
    rows = frappe.get_all(
        "File Version",
        filters={"file": file},
        fields=["name", "at_seq", "creation"],
        order_by="at_seq desc, creation desc",
        limit=1,
    )
    return rows[0] if rows else None


# --------------------------------------------------------------------------- #
# Reading them back
# --------------------------------------------------------------------------- #

#: The panel's groups, in the order it draws them. Bucketed on the server
#: rather than in the browser because the boundaries are the reader's midnight,
#: and a page that recomputes them at midnight regroups itself under the cursor.
GROUPS = ("Named", "Today", "Yesterday", "This week", "Earlier")


def timeline(file: str, kind: str, offset_minutes: int = 0, limit: int = 60) -> dict:
    """Every version of one file, newest first, grouped for the panel."""
    _store(kind).may_read(file)

    rows = frappe.get_all(
        "File Version",
        filters={"file": file},
        fields=["name", "title", "manual", "at_seq", "saves", "byte_size",
                "owner", "creation"],
        order_by="creation desc",
        limit=cint(limit) or 60,
    )

    head = cint(_body(kind, file).get("head_seq"))
    edge = _midnights(cint(offset_minutes))
    groups = {name: [] for name in GROUPS}
    for row in rows:
        groups[_group(row, edge)].append(_shape(row, head))

    return {
        "file": file,
        "head_seq": head,
        "groups": [{"label": name, "versions": groups[name]}
                   for name in GROUPS if groups[name]],
    }


def _midnights(offset_minutes: int) -> dict:
    """Today's, yesterday's and last week's boundaries, in server time."""
    from datetime import timedelta

    local = now_datetime() + timedelta(minutes=offset_minutes)
    today = local.replace(hour=0, minute=0, second=0, microsecond=0)
    back = timedelta(minutes=offset_minutes)
    return {
        "today": today - back,
        "yesterday": today - timedelta(days=1) - back,
        "week": today - timedelta(days=7) - back,
    }


def _group(row: dict, edge: dict) -> str:
    if row.get("manual"):
        return "Named"
    at = get_datetime(row["creation"])
    if at >= edge["today"]:
        return "Today"
    if at >= edge["yesterday"]:
        return "Yesterday"
    if at >= edge["week"]:
        return "This week"
    return "Earlier"


def _shape(row: dict, head: int) -> dict:
    return {
        "name": row["name"],
        "title": row["title"],
        "manual": bool(row["manual"]),
        "saves": cint(row["saves"]),
        "byte_size": cint(row["byte_size"]),
        "by": row["owner"],
        "at": str(row["creation"]),
        # The one thing the panel cannot work out for itself: whether what a
        # version holds is what is on screen right now.
        "current": cint(row["at_seq"]) == head,
    }


def payload_of(version: str, kind: str) -> str:
    """One version's body, for previewing or diffing it against the current one."""
    row = frappe.db.get_value(
        "File Version", version, ["file", "kind", "payload"], as_dict=True
    )
    if not row or row.kind != kind:
        frappe.throw(_("There is no such version."), frappe.DoesNotExistError)
    store = _store(kind)
    store.may_read(row.file)
    return store.readable(row.payload or "")


# --------------------------------------------------------------------------- #
# Changing them
# --------------------------------------------------------------------------- #

def restore(version: str, kind: str) -> dict:
    """Put a version back, keeping the one it replaced.

    Non-destructive on purpose, and the sequence matters: the current body is
    named and kept *before* the older one is written over it, so "restore" is
    never the click that loses an afternoon.
    """
    row = frappe.db.get_value(
        "File Version", version, ["file", "kind", "payload", "title"], as_dict=True
    )
    if not row or row.kind != kind:
        frappe.throw(_("There is no such version."), frappe.DoesNotExistError)

    store = _store(kind)
    store.may_write(row.file)

    keep(row.file, kind, title=_("Before restoring “{0}”").format(row.title), manual=True)
    head = store.put(row.file, row.payload or "")

    return {"file": row.file, "head_seq": head}


def rename(version: str, kind: str, title: str) -> dict:
    """Name a version, which is also what makes it survive the pruner.

    An empty name takes it back: the row keeps its payload, gets its timestamp
    back as a title, and rejoins the automatic ones the nightly thinning can
    reach. That is what "clear this name" means, and it is one endpoint rather
    than two because a name and its absence are the same field.
    """
    row = frappe.db.get_value(
        "File Version", version, ["file", "kind", "creation"], as_dict=True
    )
    if not row or row.kind != kind:
        frappe.throw(_("There is no such version."), frappe.DoesNotExistError)
    _store(kind).may_write(row.file)

    clean = (title or "").strip()[:TITLE_MAX]
    if clean:
        frappe.db.set_value("File Version", version, {"title": clean, "manual": 1})
        return {"name": version, "title": clean, "manual": True}

    stamp = frappe.utils.format_datetime(get_datetime(row.creation), "d MMM, HH:mm")
    frappe.db.set_value("File Version", version, {"title": stamp, "manual": 0})
    return {"name": version, "title": stamp, "manual": False}


def copy_out(version: str, kind: str, title: str = "") -> dict:
    """A new file holding what this version held.

    The other half of restore, and the one people reach for more often: keep
    what is there, and open the old draft beside it. The copy is a new `File`,
    so it lands in the same folder with the same sharing rules as anything else
    made here.
    """
    row = frappe.db.get_value(
        "File Version", version, ["file", "kind", "payload", "title"], as_dict=True
    )
    if not row or row.kind != kind:
        frappe.throw(_("There is no such version."), frappe.DoesNotExistError)

    store = _store(kind)
    store.may_read(row.file)

    folder = frappe.db.get_value("File", row.file, "folder") or ""
    named = (title or "").strip()[:TITLE_MAX]
    if not named:
        was = frappe.db.get_value("File", row.file, "file_name") or "Copy"
        named = f"{was} — {row.title}"

    return store.copy(row.payload or "", named, folder)


def forget(version: str, kind: str) -> dict:
    row = frappe.db.get_value("File Version", version, ["file", "kind"], as_dict=True)
    if not row or row.kind != kind:
        frappe.throw(_("There is no such version."), frappe.DoesNotExistError)
    _store(kind).may_write(row.file)

    frappe.delete_doc("File Version", version, ignore_permissions=True, force=True)
    return {"forgotten": version}


def on_trash(doc, method=None):
    """A file's versions go when the file does.

    Registered on `File`, the same way the bodies are: without it the bin's
    thirty-day sweep leaves every version of everything anybody threw away.
    """
    if doc.get("custom_kind") not in KINDS:
        return
    for row in frappe.get_all("File Version", filters={"file": doc.name}, pluck="name"):
        frappe.delete_doc("File Version", row, ignore_permissions=True, force=True)


# --------------------------------------------------------------------------- #
# Thinning them
# --------------------------------------------------------------------------- #

def thin() -> dict:
    """Nightly: drop the automatic versions the tiers say are too dense.

    Frappe's rollup, over our rows. Named versions are not in the query at all,
    so no amount of ageing can reach one.
    """
    now = now_datetime()
    files = frappe.get_all("File Version", filters={"manual": 0}, pluck="file",
                           distinct=True)

    dropped = 0
    for file in files:
        rows = frappe.get_all(
            "File Version",
            filters={"file": file, "manual": 0},
            fields=["name", "creation"],
            order_by="creation desc",
        )
        for name in _surplus(rows, now):
            frappe.delete_doc("File Version", name, ignore_permissions=True, force=True)
            dropped += 1
        frappe.db.commit()

    return {"files": len(files), "dropped": dropped}


def _surplus(rows: list[dict], now) -> list[str]:
    """Which of these automatic versions the tiers do not have room for."""
    drop = []
    kept_at = None
    for row in rows:
        at = get_datetime(row["creation"])
        age = (now - at).total_seconds() / 3600
        if age > FORGET_AFTER_HOURS:
            drop.append(row["name"])
            continue
        spacing = _spacing(age)
        if spacing <= 0:
            kept_at = at
            continue
        if kept_at is not None and (kept_at - at).total_seconds() / 3600 < spacing:
            drop.append(row["name"])
            continue
        kept_at = at
    return drop


def _spacing(age_hours: float) -> float:
    """Hours that must separate two kept versions of this age."""
    for older_than, spacing in TIERS:
        if age_hours <= older_than:
            return spacing
    return float(FORGET_AFTER_HOURS)


# --------------------------------------------------------------------------- #
# What the panels call
#
# One family for both kinds, with `kind` a parameter rather than two families
# that would be the same code twice. Every one of them ends in the store's own
# permission check, so a version is exactly as readable as the file it came
# from.
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def history(file: str, kind: str, offset_minutes: int = 0, limit: int = 60) -> dict:
    """Every version of one file, grouped the way the panel draws them."""
    return timeline(file, kind, cint(offset_minutes), cint(limit))


@frappe.whitelist(methods=["GET"])
def version_body(version: str, kind: str) -> dict:
    """One version's stored body, for previewing it or diffing it against now."""
    return {"name": version, "payload": payload_of(version, kind)}


@frappe.whitelist(methods=["POST"])
def save_version(file: str, kind: str, title: str = "") -> dict:
    """Keep this moment by name. The one version the policy never refuses."""
    _store(kind).may_write(file)
    name = keep(file, kind, title=title, manual=True)
    return {"name": name}


@frappe.whitelist(methods=["POST"])
def restore_version(version: str, kind: str) -> dict:
    """Put a version back. The one it replaces is named and kept first."""
    return restore(version, kind)


@frappe.whitelist(methods=["POST"])
def name_version(version: str, kind: str, title: str = "") -> dict:
    """Name a version, which is also what makes the nightly pruner leave it."""
    return rename(version, kind, title)


@frappe.whitelist(methods=["POST"])
def forget_version(version: str, kind: str) -> dict:
    """Throw one version away. The body it was taken from is untouched."""
    return forget(version, kind)


@frappe.whitelist(methods=["POST"])
def copy_version(version: str, kind: str, title: str = "") -> dict:
    """Open an earlier draft as a new file, leaving this one where it is."""
    return copy_out(version, kind, title)
