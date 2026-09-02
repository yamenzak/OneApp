# Working on OneSpace

## How to answer me

I am the only person reading this and I already know what we are building.

* **Lead with the answer.** One or two sentences that would satisfy me if I read
  nothing else.
* **Under 150 words.** 300 if it is genuinely long.
* **No headers, no bold-label lists, no tables** unless I asked for a comparison
  or there are three-plus parallel items.
* **Say the thing, not the shape of the thing.** "The bell writes a
  `Document Follow` row" — not "**The control.** A bell beside the heart…".
* **One caveat, not five.** The one that would change what I do.
* **Do not restate work I just watched you do.** A commit hash and one line is a
  complete report.
* **Never re-explain a decision I already agreed to.**

Long form goes in commit messages, `docs/` and code comments. `/bro` means it
did not land — re-explain it simply.

## Where things are

* **`docs/ONESPACE.md`** — the product. Spaces, screens, the four view bodies,
  the record, roles, collaboration, printing, the UI rules, what is not built.
* **`docs/ONEADMIN.md`** — the platform. Tenancy, the control plane, the
  operator console, billing, credits, storage, the lifecycle, configuration,
  bring-up, and how to work on this repo.
* `docs/PRINTING.md` and `docs/WORKSPACE-SETTINGS.md` are reference tables that
  tests read back.

## Two rules that are nowhere else

* **OneApp is the repository name and is never product-facing.** The product is
  OneSpace; the operator console is OneAdmin.
* **`frappe/central`, `frappe/atlas` and `frappe/crm` are AGPL-3.0 and this repo
  is MIT.** Read them for patterns, never copy code. Anything that is really a
  frappe-ui component comes from frappe-ui, which is MIT.
