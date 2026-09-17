# AI

**OneCalendar declares no `@ai_feature` of its own**, and one of OneAI's
suggestion kinds is about it.

## The diary card

`oneai/kinds.py` holds the suggestion kinds for the framework's own nouns — a
record, a task, **a date in somebody's diary** — and that last one writes an
`Event`. It is the single file in the AI spine allowed to import a module, and
this is the module it imports: `tests/test_ai_layering.py` names the exception
one file at a time so the next one has to argue its case.

The shape is OneAI's throughout. A model cannot write. What it can do is put a
card in front of somebody — *this date, this title, this hour* — and the write
happens later, in a request a person made by pressing Apply, through
`diary.save_event`, which is the same function the dialog posts to.

So a mail that says "let's meet Thursday at three" offers a card, and pressing
it makes exactly the event the reader could have made by hand.

## What a tenant configures

Nothing here. The dials are OneAI's: the workspace's model, its per-feature
switches, its ceiling. There is no calendar row in that list, because there is
no calendar feature — the card belongs to whichever feature *proposed* it,
which is usually mail's.

## Not built

Reading the calendar back. The assistant's toolbox (`oneai/chat/toolbox.py`)
can read the Drive and a space's records, and it cannot yet answer "what does
my Thursday look like" — which is `diary.agenda` with a range, and is a tool
wrapper rather than a feature. It waits on nothing except being written.
