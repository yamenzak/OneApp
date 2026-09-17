# AI

**OneTask declares no `@ai_feature` of its own**, and one of OneAI's suggestion
kinds is a task.

## The task card

`oneai/kinds.py` holds the suggestion kinds for the framework's own nouns — a
record, a date in a diary, **a task** — and it is the one file in the AI spine
allowed to import a module, named one file at a time in
`tests/test_ai_layering.py` so the next one has to argue its case.

The shape is OneAI's throughout and the important half is what it refuses. A
model cannot write. What it can do is put a card in front of somebody — *this
subject, this project, this person* — and the write happens later, in a request
a person made by pressing Apply, through the same path a person typing into the
capture box goes through.

So a mail that says "can you send the revised drawings by Friday" offers a card,
and pressing it makes exactly the task the reader could have made by hand, in
the Inbox, with no project, because that is what an unplaced thought is.

## Why capture is not an AI feature

The service's capture box is a text input that writes a subject, and it is
deliberately not "describe what you want and a model will fill in the fields".
The whole claim of the window is that **a thought costs one keystroke**, and a
round trip to a model is not one keystroke — it is two seconds and a thing that
might be wrong about the project.

## What a tenant configures

Nothing here. Every dial is OneAI's: the workspace's model, the per-feature
switches, the ceiling. There is no OneTask row in that list because there is no
OneTask feature — the card belongs to whichever feature proposed it, usually
mail's or the assistant's.

## Not built

**Asking the assistant about the work.** `oneai/chat/toolbox.py` reads a
space's records through the same endpoints the SPA calls, and OneProject is a
space, so "what is open on REEM" is already answerable the ordinary way. What
is not there is anything task-shaped in the toolbox — a wrapper over
`service.now()` — and it is not obviously worth one: the general tool already
reaches the rows.
