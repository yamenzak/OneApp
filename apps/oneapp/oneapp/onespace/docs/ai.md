# AI

**The engine declares no `@ai_feature`.** Since stage 3b of the cleanup arc it
does not even contain the AI code — `oneai/` is a module of its own. What is
left here is the three seams OneAI reaches through, and they are worth reading
as a set because together they are the product's whole AI safety argument.

## `spaceview.resolve` — what the assistant may look at

Every tool in `oneai/chat/toolbox.py` is a wrapper over an endpoint the SPA
already calls, and most of them land here. So the assistant resolves a space
and a screen **as the asker**, through the same checks a click goes through,
and sees exactly what its asker could click to.

`oneai/chat/context.py` binds the space onto the tools and out of their
schemas, so a model cannot even *name* a space the asker does not hold.

## `spaceview.records.save` — what an Apply goes through

A model cannot write. `oneai/actions.apply_suggestion` is a request a **person**
makes by pressing Apply, and it runs through the same function the record form
posts to — the same field allowlist, the same validation.

That is why a suggestion cannot reach a field a person could not: there is no
second write path to secure.

## `onespace_chat_tools` — how a module adds its own

The hook. OneHR registers two (`my_hr_standing`, `who_is_in`) and
OneMobility registers its own, and both exist because the engine's eight
record tools answer "find, count, read" and some questions are not about
records.

A tool is **not** a feature: no model, no price, no switch. What a workspace
turns off is `chat.workspace`, and the tools go with it.

## One dependency points the wrong way, and is known

`sync.py` and `spaceview/records.py` import `oneapp.oneai`. The engine reaching
into a service is backwards — a service is meant to depend on the engine — and
it predates stage 3b, when both were in this directory and the import was
invisible.

It is written down here rather than quietly left because
`tests/test_ai_layering.py` guards the *other* direction (the spine must not
import a module) and nothing guards this one. Untangling it is not free: what
the engine wants is the index kept in step on save, which is genuinely an event
the engine is best placed to raise.

## What a tenant configures

Nothing here. Every dial is `OneAI Settings`, and `oneai/docs/ai.md` is the
list.
