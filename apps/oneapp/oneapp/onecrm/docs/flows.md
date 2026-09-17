# Flows

    progress    the shared stage-log walk
    deal        ERPNext's Opportunity, subclassed
    lead        ERPNext's Lead, subclassed
    stages      the pipeline a workspace owns
    calls       a call as a record, and the verbs that log one
    answering   the promise about responding, measured

## Moving a deal — `progress.log_the_move`

One function, two callers, because a lead and a deal have the same question and
different field names:

1. Read the stage field (`sales_stage` on a deal, `qualification_status` on a
   lead).
2. If the last log row is still open and names the same stage, do nothing.
3. Otherwise close the open row — `left_on`, and `days` from the hours between
   — and append a new one.
4. Trim to `MOST` (100) rows and set `custom_stage_since`.

Guarded on `doc.meta.has_field(log)`, because custom fields are applied by the
seeder and not by migrate: a site that has not seeded yet would otherwise throw
on every save.

## Weighting a deal — `deal._weigh`

`custom_weighted_amount` is the amount times the probability. Rounded to the
field's own precision, which is the only interesting part.

## Logging a call — `calls.py`

Four whitelisted wrappers, one per surface — `about_a_deal`, `about_a_lead`,
`about_a_contact`, `about_an_organisation` — each answering the same shape:

    {"create": {"screen": "calls", "values": {...}}}

An action verb that says *what happens next* rather than doing it, which is the
engine's own vocabulary. `_held` filters the candidate fields through
`frappe.get_meta(...).has_field`, so a site missing a field offers one fewer
box rather than failing.

`entries(doctype, name, resolved)` is the timeline source, keyed `call:{name}`
and **timed by `at` rather than by `creation`** — a call logged on Thursday
about Tuesday belongs on Tuesday.

## Answering, measured — `answering.py`

The feature in order:

1. **`apply(doc)`** on validate. Finds the target that covers this record —
   `matches(doc, rules)`, an AND over nine operators, no `eval`, and a missing
   field is False — then the level for its priority, then writes **both**
   deadlines once per round.
2. **`deadline(start, target, hours)`** walks the working week forward,
   skipping days that do not work and the holiday list. A day with no stated
   window ends at **midnight of the next day**, never 23:59:59 — the second
   that was being lost per crossing.
3. **`answered()`** stops the respond clock; **`reopened()`** starts a new
   round.
4. **`on_communication`** — Sent means answered, Received means reopened.
   **`on_call`** — Outgoing means answered, anything else reopened.
5. **`late_now()`** runs per clock and sweeps what has passed its deadline.

**Rolling is the half that is easy to get wrong.** A conversation is not one
question: a customer replies and the clock starts again. `custom_rounds` counts
how many times, and `custom_round_began` is when the current one started.

`worked_hours(start, end, target)` is the inverse walk — how much working time
actually passed — which is what `custom_answered_in` records.

## Setting the targets up — `answering.ensure(targets)`

Writes `position` **from the order of the list**, which is the whole fix for
the bug in `collections.md`: without it every target ties at 0 and the
tie-break is the name.
