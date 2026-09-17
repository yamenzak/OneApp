# Permissions

**OneAI has no roles**, and the permission model is the sentence that makes the
whole thing safe: **the assistant sees exactly what its asker could click to.**

## Every tool is a wrapper over an endpoint the SPA already calls

`chat/toolbox.py` does not query. It calls `spaceview.resolve`,
`spaceview.records.rows`, `spaceview.records.record`, `onestorage.query` — the
same functions a button in the browser calls, as the same user, through the
same checks.

So a person who cannot open OnePeople's payslips cannot get the assistant to
read one, and nothing in this module had to know what a payslip is. The
alternative — a tool that queries directly with `ignore_permissions` and a
filter it applies itself — is a second permission model, and a second one is a
place for the two to disagree.

`chat/context.py` binds the space onto the tools and out of their schemas, so
the model cannot even *name* a space the asker does not hold.

## No tool writes

The `propose_` tools record what would change and return "waiting". The write
is `actions.apply_suggestion`, **a request a person makes by pressing Apply**,
running as them, through `spaceview.records.save` — the same field allowlist and
the same validation a record form gets.

`before` on the suggestion is what the record said when the card was made, so
an Apply against a record that moved underneath is refused rather than
silently overwriting somebody.

## Who may change the settings

`settings.update` and `index.rebuild` require the **workspace owner** —
`onespace.workspace.require_owner`. Picking the model, setting the ceiling and
naming the assistant are decisions about what the workspace spends and what
character every colleague meets, not preferences.

`settings.get` is readable by anybody in the workspace, because a person whose
verb is greyed out needs the sentence saying why.

## The credit ceiling is a permission of a kind

`meter.py` holds credits **before** the call and settles after. A call nobody
can pay for does not start. It is the only place in the product where running
out of something is a refusal rather than a queue, and `OutOfCredits` is part of
the small gateway surface a module may catch.

## What a workspace may switch off, and what it may not

`ai_enabled` off stops every feature a workspace is **allowed** to stop.
Features declared as critical keep running — they are the process, not an
assistant beside it. That distinction is on the feature declaration and not on
the settings row, so a workspace cannot switch off something the product needs
to work by ticking a box.
