"""A `Transit Source` that carried its own SFTP credentials becomes a mount.

The first shape change under a site that already exists, and it is here rather
than left to a hand-edit because the credential is in `__Auth`: a person
retyping it into the new form needs the password, and the whole point of
moving it is that they no longer have to hold one.

One `Remote Folder` per distinct host and username. Two sources reading two
folders on one authority's box were two copies of one credential before this
and are one mount with two paths after it, which is the shape that was worth
moving to.

`base_path` stays `/` and the source keeps its own folder as the path inside
the mount, deliberately: putting the drop folder in the mount's base would
make the mount unbrowsable above it, and a person connecting this by hand
would have pointed it at the account's root.
"""

import frappe


def execute():
    if not frappe.db.has_column("Transit Source", "remote_folder"):
        return

    rows = frappe.get_all(
        "Transit Source",
        filters={"kind": "SFTP"},
        fields=["name", "endpoint", "folder", "username"],
    )
    if not rows:
        return

    made: dict[tuple[str, str], str] = {}
    for row in rows:
        host, _sep, port = (row.endpoint or "").partition(":")
        host = host.strip()
        if not host:
            # Nothing to connect to. The source keeps its folder and its
            # message says what is missing, which is better than a mount
            # pointing at an empty host.
            frappe.db.set_value("Transit Source", row.name, {
                "kind": "Folder",
                "last_message": "This source had no host. Connect a folder in "
                                "Files and name it here.",
            }, update_modified=False)
            continue

        key = (host.lower(), (row.username or "").lower())
        if key not in made:
            label = host.split(".")[0] or host
            name = label
            n = 2
            while frappe.db.exists("Remote Folder", name):
                name, n = f"{label} {n}", n + 1
            mount = frappe.get_doc({
                "doctype": "Remote Folder",
                "folder_name": name,
                "protocol": "SFTP",
                "host": host,
                "port": int(port) if port.isdigit() else 0,
                "username": row.username,
                "base_path": "/",
                # Not Connected: nothing has proved this works since it moved,
                # and a mount that says Connected without having been asked is
                # the lie this whole feature exists to stop telling.
                "status": "Paused",
                "last_message": "Moved from a transit source. Check it, then "
                                "take it off pause.",
            }).insert(ignore_permissions=True)
            made[key] = mount.name

            # The password travels with it. `get_password` on the source and
            # `set` on the mount, because both are `__Auth` rows and there is
            # no way to copy one without reading it.
            secret = frappe.utils.password.get_decrypted_password(
                "Transit Source", row.name, "secret", raise_exception=False
            )
            if secret:
                frappe.utils.password.set_encrypted_password(
                    "Remote Folder", mount.name, secret, "secret"
                )

        frappe.db.set_value("Transit Source", row.name, {
            "kind": "Folder",
            "remote_folder": made[key],
            "folder": row.folder or "/",
        }, update_modified=False)

    frappe.db.commit()
