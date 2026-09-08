"""What a module declares, and where it declares it.

Two kinds of declaration, both made from the module the fact belongs to:

* a **clause** — a paragraph that has to appear in one of the documents,
  because of something that module does;
* a **subprocessor** — a third party that module hands customer data to.

Both are registered by calling a function at import time from
`<module>/legal.py`. Import time rather than a scan of the source, because a
clause that has to be found by a regular expression is a clause somebody will
break by reformatting it.

The ordering is deliberate and dull: within a section, clauses come out in
`(order, module, key)` order. A stable order means the assembled document's
hash only changes when the *text* changes, so a version bump means what it says.
"""

#: `(document, section)` -> list of clause dicts. Filled at import time.
CLAUSES: dict[tuple[str, str], list[dict]] = {}

#: name -> subprocessor dict. A name may be declared once; two modules using
#: Cloudflare declare the *purposes* they use it for, not two Cloudflares.
SUBPROCESSORS: dict[str, dict] = {}


def clause(*, document: str, section: str, key: str, module: str, body: str,
           order: int = 100, heading: str = "") -> None:
    """Register one paragraph of one document.

    `key` is stable and unique within its document: it is what a translation
    keys off and what a diff of two versions is expressed in.
    """
    body = " ".join(body.split())
    if not body:
        raise ValueError(f"{module}: clause {key} has no text")

    slot = CLAUSES.setdefault((document, section), [])
    if any(one["key"] == key for one in slot):
        raise ValueError(f"clause {key} is declared twice in {document}/{section}")
    slot.append({
        "key": key, "module": module, "heading": heading,
        "body": body, "order": order,
    })


def subprocessor(*, name: str, purpose: str, module: str, data: str,
                 where: str, safeguard: str, url: str = "") -> None:
    """Register a third party that receives customer data.

    Everything a subprocessor list has to say and nothing it does not: who they
    are, what for, what they get, where that sits, and what makes the transfer
    lawful.

    One company is one row with several uses, because "who are your
    subprocessors" is a question about companies. What a company *does* varies
    by use and so does where it does it — Cloudflare keeps a workspace's files
    in the region it chose and runs a model on whichever of its locations is
    nearest — so `where` belongs to the use. The safeguard is the contract we
    have with the company, so that belongs to the company, and declaring two
    different ones is an error rather than a second row.
    """
    entry = SUBPROCESSORS.get(name)
    use = {"module": module, "purpose": purpose, "data": data, "where": where}

    if entry is None:
        SUBPROCESSORS[name] = {
            "name": name, "url": url, "safeguard": safeguard, "uses": [use],
        }
        return

    if entry["safeguard"] != safeguard:
        raise ValueError(
            f"{name} is declared with two different safeguards; the contract "
            "with a company is one contract"
        )
    entry["uses"].append(use)


def clauses_for(document: str, section: str) -> list[dict]:
    """One section's clauses, in the order they will be read."""
    found = CLAUSES.get((document, section), [])
    return sorted(found, key=lambda one: (one["order"], one["module"], one["key"]))


def subprocessor_rows() -> list[dict]:
    """Every subprocessor, alphabetically, with its purposes in module order."""
    rows = []
    for entry in sorted(SUBPROCESSORS.values(), key=lambda one: one["name"].lower()):
        rows.append({
            **entry,
            "uses": sorted(entry["uses"], key=lambda one: (one["module"], one["purpose"])),
        })
    return rows


def reset() -> None:
    """Empty both registries. For tests, and for nothing else."""
    CLAUSES.clear()
    SUBPROCESSORS.clear()
