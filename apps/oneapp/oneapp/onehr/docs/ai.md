# AI

**OneHR declares no `@ai_feature`**, and it is the module that added two
assistant **tools** — the only two outside the engine's own.

## Why the engine's eight were not enough

`oneai/chat/toolbox.py` ships eight tools and they are about *records*: find
them, count them, read one. That is right for almost every question and wrong
for the two this module exists to answer.

**"How much leave have I got left"** is an allocation minus what was taken
against it. `history.py` computes it and no filter expresses it.

**"Am I checked in"** is the last punch read against a shift. `presence.py`
works it out and it is not a field on anything.

A model given only the record tools answers both by listing Leave Applications
and guessing.

## The two tools

`assistant.py`, registered through the `onespace_chat_tools` hook:

**`my_hr_standing`** — the reader's own: their job, whether they are in today,
what is left of each leave type, what they have asked for and what is coming
up.

**`who_is_in`** — the row of faces on the home page, as words. Manager, peers
and reports, each with whether they are in, on leave or absent. It takes a
name, so "is Hala in today" is one call rather than a list and a filter.

## Both go through `own.may_read`

Which is the point, and is the same rule OneAI's own `permissions.md` states:
the assistant sees exactly what its asker could click to. `my_hr_standing`
resolves the asker to their own `Employee`; `who_is_in` answers about their
manager, peers and reports — **presence**, not records.

So a `HR-User` asking about a colleague's leave balance gets nothing, and this
module did not have to write a second check to make that true.

## What a tenant configures

Nothing here. A tool is not a feature — it has no model, no price and no
switch of its own. What a workspace turns off is `chat.workspace`, and the
tools go with it.

## What is deliberately not offered

**Anything that writes.** No tool here asks to file leave, mark attendance or
approve a request. Filing leave for somebody is a decision, and the suggestion
model exists so a model can offer a card rather than take one — but nobody has
written the kinds, and until somebody has thought about what "a model proposed
your absence" should look like on the record, offering it would be worse than
not.

**The confidential lane.** Nothing in the toolbox reaches level-2 fields, and
that falls out of `may_read` rather than being a rule of its own: the tools
read what the asker reads, and `ctc` is `HR-Admin`'s. Worth stating anyway,
because "the assistant cannot tell you what somebody earns" is the question a
workspace will actually ask.
