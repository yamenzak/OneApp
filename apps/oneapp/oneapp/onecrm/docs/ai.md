# AI

**OneCRM declares no `@ai_feature` of its own**, and it is on the receiving end
of the most interesting one in the product.

## Filing a message against a deal

`onemail/filing.py` declares `mail.file`, and what it asks a model for is a
**ranking of candidates with a reason** rather than an answer. The candidates
come from `oneai/index.py`'s embeddings, so a message is matched against
records that already look related.

A deal is one of those candidates, and when it wins, what lands is a
`Communication Link` with `custom_link_by` saying a model made it. That
provenance column is what lets the desk offer to undo exactly that class of
link and leave the ones a rep made alone.

`docs/DOCUMENT-MAIL.md` is the argument for why the lane is worth its cost, and
a CRM is the reason: "which deal is this email about" is the question a sales
desk asks fifty times a day and answers by hand.

## What the assistant can already do here

`oneai/chat/toolbox.py` reads a space's records through the same endpoints the
SPA calls, and OneCRM is a space — so "what is still open in the pipeline" and
"who have we not rung back" are answerable the ordinary way, as the asker,
through the asker's own seat. A `CRM-User` asking gets a `CRM-User`'s answer.

## What a tenant configures

Nothing here. The dials are OneAI's, and the one that matters to this space is
`mail.file`: a cautious workspace switches it off and keeps `linking.py`'s
rules, which works because the rules are the base case and the model is the
fallback.

## What would be worth building, in order

1. **A summary on a deal's timeline.** `text.summarise` already exists and a
   deal already has a timeline of everything at once — calls, mail, stage
   changes. "What happened on this deal" is one feature away and is the thing a
   manager asks before a review.
2. **A next step, from the stage log.** `One Stage Change` records how long a
   deal sat in each stage. A model reading that against deals that closed is
   the only genuinely CRM-shaped AI feature on the list, and it needs enough
   closed deals to be worth asking — which a new workspace does not have.

Neither is built. The first is small and the second is the interesting one.
