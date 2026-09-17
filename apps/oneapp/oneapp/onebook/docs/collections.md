# Collections

**OneBook owns no doctypes.** There is no `onebook/doctype/` directory and
`OneBook` is not in `modules.txt`, which is the same shape as OnePeople and
OneProject and for the same reason: `docs/ERP-SPACES.md`. A general ledger is a
solved problem, a second one is a set of books that disagrees with the first,
and everything below is ERPNext's.

## Borrowed — the ones a screen is built on

| Doctype | From | What it is here |
| --- | --- | --- |
| `Sales Invoice` | ERPNext | What we are owed. The Invoices screen, and half of the checkpoint this space was built for. |
| `Purchase Invoice` | ERPNext | What we owe. The Bills screen. |
| `Payment Entry` | ERPNext | Money that moved, in either direction. |
| `Journal Entry` | ERPNext | Everything the other three could not say — including what a payroll run posts. |
| `GL Entry` | ERPNext | The ledger itself. Read-only everywhere, because nothing in ERPNext writes one by hand either. |
| `Account`, `Cost Center` | ERPNext | The chart, drawn as the tree it is. The Admin seat's. |
| `Fiscal Year`, `Accounting Period` | ERPNext | When the books open and when they close. |
| `Bank Transaction`, `Bank Account`, `Bank` | ERPNext | The feed and what it reconciles against. |
| `Supplier`, `Supplier Group` | ERPNext | Who we pay — see the README §3 for why the party lives here and not in OneCRM. |
| `Mode of Payment`, `Payment Terms Template`, `Sales Taxes and Charges Template`, `Purchase Taxes and Charges Template` | ERPNext | Four tables behind the Configuration page. |
| `Customer`, `Item`, `Company`, `Currency`, `Project` | ERPNext | Read, never written. Each is owned by another space and resolved here as a link. |
| `Salary Slip`, `Payroll Entry`, `Expense Claim`, `Employee` | HRMS | What OnePeople raised, read from the paying side. |
| `OneSpace Saved View`, `OneSpace Word` | ours | The engine's own two, as every space has them. |

## The custom field

One, declared in `oneapp_control/spaces/onebook.py` and applied to four
doctypes.

**`custom_origin`** — a read-only `Data` holding the space id that raised the
document, or nothing at all. Written by `onebook/origin.py` on `validate` and by
nothing else; the README §2 is the argument for it and the reason it is a cache
of a join rather than a field.

It is on `Sales Invoice`, `Purchase Invoice`, `Payment Entry` and
`Journal Entry` — the four documents that can arrive from somewhere else. The
set is named once, as `POSTED_INTO`, in both the manifest and `origin.py`, and
`tests/test_onebook_origin.py` holds the two together.

## What was left out

One hundred and seventy-odd doctypes of ERPNext's Accounts module, and the
number is worth stating rather than apologising for. A bookkeeper uses about a
dozen tables and a business owner about four. What is missing is somebody else's
job (`Sales Order`, `Purchase Receipt`), a setting reached through the
Configuration page, or a desk report this product draws as a dashboard over a
list it already has.
