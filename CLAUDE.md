# Working on OneSpace

## How to answer me

Short. Plain. I am the only person reading this, and I already know what we
are building.

* **Lead with the answer.** One or two sentences that would satisfy me if I
  read nothing else. Detail goes after that, or nowhere.
* **A normal reply is under 150 words.** A long one is under 300. If it is
  going past that, something is being explained that I did not ask about.
* **No headers, no bold-label lists, no tables** unless I asked for a
  comparison or there are genuinely three-plus parallel items. Prose in short
  paragraphs beats a formatted wall.
* **Say the thing, not the shape of the thing.** "The bell writes a
  `Document Follow` row" — not "**The control.** A bell beside the heart in
  the record header, over `spaceview.toggle_follow`."
* **One caveat, not five.** Pick the one that would actually change what I do.
  The rest belongs in the commit message or the docs, which is where I go
  looking for it.
* **Do not restate the work I just watched you do.** A commit hash and one
  line of what changed is a complete report.
* **Never re-explain a decision I already agreed to.**

Long form belongs in commit messages, in `docs/`, and in code comments. Those
are read once, deliberately, by somebody looking for them. A chat reply is
read now, in a hurry, by me.

If a reply did not land, I will type `/bro` and you re-explain it simply —
see `.claude/skills/bro/`.

## Everything else

The architecture, the decisions and the reasoning live in `docs/`:
`ARCHITECTURE.md`, `DECISIONS.md`, `SPACES.md`, `NOTIFICATIONS.md`,
`LIFECYCLE.md`, `AI.md`, `FRAPPE-UI.md`, `DEVLOOP.md`, `RUNBOOK.md`.

Two rules that are not in there:

* **OneApp is the repository name and is never product-facing.** The product
  is OneSpace.
* **`frappe/central`, `frappe/atlas` and `frappe/crm` are AGPL-3.0 and this
  repo is MIT.** Read them for patterns; never copy code. Anything that is
  really a frappe-ui component comes from frappe-ui, which is MIT.
