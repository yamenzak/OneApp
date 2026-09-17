# Collections

The engine's doctypes are **about the workspace rather than about a
department**. Fourteen of them, and they fall into four groups.

## What a reader has done to a screen

| Doctype | What it is |
| --- | --- |
| `OneSpace Saved View` | A reader's own filters, columns and sort, on one screen. Shareable. |
| `OneSpace Hidden View` | A shared view somebody dismissed. A row saying "not for me" rather than a deletion of somebody else's work. |
| `OneSpace Word` | The workspace's own word for a screen somebody else named — Deals as *Donations*. |

## What the site knows about itself

| Doctype | What it is |
| --- | --- |
| `OneSpace Site State` (single) | The last synced manifest: `spaces_json`, `roles_json`, and the rest of what the control plane sent. |
| `OneSpace Map Settings` (single) | Where a map gets its ground — the basemap a workspace uses. |

## Bringing somebody's old system in — the importer

| Doctype | What it is |
| --- | --- |
| `Import Source` | Where the data is coming from. |
| `Import Plan` | What will be made from it. |
| `Import Step` | One stage of that plan. |
| `Import Run` | One execution. |
| `Import Run Step` | One stage of one execution. |
| `Import Issue` | A row that would not go in, and why. |
| `Import Identity` | What a row from over there became over here, so a second run recognises it. |

Seven doctypes, which is a feature the size of a small module sitting inside
the engine — and `docs/CLEANUP.md` §3b names it as a candidate to leave.

## The cross-cutting two

| Doctype | What it is |
| --- | --- |
| `Bound Record` | A record something else reads, **by key**. A document names `quotation.grand_total`; the binding says which quotation. Shared by OneWriter and OneWorkbook. |
| `Compliance Document` | A document a workspace has to hold — a licence, an insurance certificate — with an expiry that `expiry.py` walks daily. |

## What is not a doctype, and is the interesting half

**A screen is not a row here.** It is a `OneSpace Space Screen` on the *control
plane*, and a tenant holds the whole manifest as JSON on `OneSpace Site State`.
The engine resolves that JSON against this site's own metadata on every read.

**A seat is not a row.** `<prefix>-<Seat>`, derived. `seats.py` is the whole of
it on this side.

**A twin is not a screen.** `@me` in a screen's own filters, resolved by
`mine.py`.

**A word a workspace changed is** a row (`OneSpace Word`) because it is data
somebody typed; the screen it renames is not.
