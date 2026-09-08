"""What enabling and disabling this space actually does.

A space that only appears in a launcher is cheap to add and cheap to remove. A
space with fact tables is not: enabling it creates them, and removing it has to
mean the data is gone rather than orphaned in a database nobody looks at.

Both halves are here so the answer to "what happens to my data when I turn this
off" is one file rather than a search.
"""

import frappe
from frappe import _

from ..shared import facts
from . import model

#: The reference doctypes, in the order they can safely be deleted — children
#: before parents, so a link never dangles mid-way through.
RECORDS = (
    "Transit Feed",
    "Transit Line",
    "Transit Stop",
    "Transit Vehicle",
    "Transit Agency",
    "Transit Source",
)


def on_enable():
    """Create the fact tables. Idempotent, so a re-enable is not a migration."""
    model.ensure_all()
    frappe.db.commit()


def on_disable(delete_data: bool = False):
    """Stop the space, and optionally take its data with it.

    **Not** destructive by default. Turning a space off is usually somebody
    tidying a launcher, and a launcher tidy that silently drops four years of
    telemetry is the worst thing this product could do. The data stays, the
    tables stay, and re-enabling finds everything where it was.

    `delete_data` is the deliberate second act — the one the workspace settings
    surface asks about in words, with the count in front of the person pressing
    it. It writes an audit entry first, because a deletion nobody can account
    for later is indistinguishable from a bug.
    """
    if not delete_data:
        return {"deleted": False}

    counted = {name: frappe.db.count(name) for name in RECORDS}
    readings = 0
    if facts.exists(model.OBSERVATION):
        readings = frappe.db.sql(f"SELECT COUNT(*) FROM `{model.OBSERVATION.table}`")[0][0]

    # The audit entry before the deletion, not after: a process that dies
    # halfway should leave a record that it was asked, not silence.
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Deleted",
            "reference_doctype": "OneSpace Space",
            "reference_name": "onemobility",
            "content": _(
                "OneMobility data deleted on request: {0} records and {1} readings."
            ).format(sum(counted.values()), readings),
        }
    ).insert(ignore_permissions=True)
    frappe.db.commit()

    model.drop_all()
    for doctype in RECORDS:
        frappe.db.delete(doctype)
    frappe.db.commit()

    return {"deleted": True, "records": counted, "readings": readings}


@frappe.whitelist(methods=["POST"])
def forget_everything() -> dict:
    """The customer's own button for the above.

    Owner-only, because it is not recoverable and is not a thing an invited
    user should be able to do to somebody else's four years of history.
    """
    from ..onespace.workspace import require_owner

    require_owner()
    return on_disable(delete_data=True)
