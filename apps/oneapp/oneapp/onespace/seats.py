"""The four seats a space has, on the tenant's side of the wire.

Every space offers exactly four: User, Manager, Audit, Admin. The Frappe role
one of them becomes is `<prefix>-<Seat>` — `HR-Manager`, `CRM-Audit` — where
the prefix is the space's `role_name`.

The control plane declares them, in `oneapp_control/spaces/roles.py`, and a
tenant site does not carry that app. The child table of roles has never
travelled in the sync payload either: a cached space holds the prefix and
nothing else. So the naming is the contract between the two halves, written
down in exactly these two places, and `tests/test_workspace_roles.py` reads one
against the other.
"""

SEATS = ("User", "Manager", "Audit", "Admin")


def role(prefix: str, seat: str) -> str:
	prefix = (prefix or "").strip()
	if not prefix or seat not in SEATS:
		return ""
	return f"{prefix}-{seat}"


def roles(prefix: str) -> list[str]:
	return [name for name in (role(prefix, seat) for seat in SEATS) if name]
