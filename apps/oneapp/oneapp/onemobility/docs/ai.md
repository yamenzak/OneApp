# AI

**OneMobility declares no `@ai_feature`**, and it registers assistant tools
through `onespace_chat_tools` the way OnePeople does.

## Why a transit space needs its own tools

The engine's eight tools are about records — find them, count them, read one —
and this space's interesting questions are about the **aggregate tier**, which
is not a doctype and has no records to find.

"Was line 12 worse than usual last week" is a percentile read against a
baseline. `network.punctuality` and `forecast.unusual` compute it and no filter
expresses it, so a model given only the record tools answers by listing
`Transit Line` rows and guessing.

## What is deliberately not offered

**Nothing that writes.** No tool asks to accept a claim, change a precedence or
re-point a source. Those are the Admin seat's, they are the decisions that can
take a map down, and a model proposing one would be a card whose Apply nobody
should press quickly.

**Nothing over raw observations.** The tools read the aggregate API like every
other reader, which means a question about where one vehicle was at one moment
is answered by the playback screen and not by the assistant. That falls out of
`permissions.md`'s central rule rather than being a separate decision.

## The forecast is not AI, and saying so matters

`forecast.py` reads percentiles out of the aggregate tier. It is arithmetic
over what actually happened — **not a model, and not a second subsystem**, but
a second reader of a tier that already existed.

It is worth writing down because "predictive" and "AI" are the same word in a
tender document, and they are not the same thing here. Nothing about the
outlook, the risk or the bunching warning sends anything to a provider, costs a
credit or can be switched off in `OneAI Settings`.

The one concrete consequence: the aggregate tier stores **percentiles rather
than means**, because a mean cannot be turned into "seven times in ten this
stop is more than four minutes late".

## What a tenant configures

Nothing here. The tools go with `chat.workspace`, and a workspace that switches
the assistant off loses them along with everything else.

## Datenschutz

README §9 is the argument and `legal.py` is the clause. What it means for this
page: positional history is the most sensitive thing this product holds, and
the answer to "does the AI see it" is that it sees what the aggregate API
returns, for entities the asker may open — never a track, never a vehicle's
day.
