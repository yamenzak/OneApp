# Notifications

**OneAI ships no `ALERTS` rows and sends no mail.** Everything a person hears
from it is in front of them at the time, and that is deliberate: an assistant
that emails you about what it did while you were away is an assistant doing
things while you were away, which is the thing the suggestion model exists to
prevent.

## What it does publish

**Over the socket, not as a notification.** A streaming run publishes its
deltas to the room the asker is in — `streaming.py`, over the socket the bench
already runs. A browser that dropped a frame fetches `result(id)`. Nothing is
persisted as a notice because the run belongs to a page somebody is looking at.

## The two things that reach a person later

**A suggestion card waits.** `OneAI Suggestion` rows outlive the conversation
that made them and are listed by `actions.suggestions`, so a card offered while
you were reading a mail is still there when you come back to the record. That
is a *list*, not a notification — nothing pushes.

**The sparkle beside a field.** `OneAI Written Value` marks a value a model
wrote. It is the quietest possible notification and the most important one: it
is how somebody reading a record a week later knows which sentence they did not
write.

## What is not built, and the argument against it

A rule saying "tell me when a long run finishes". It would be useful for the
rare forty-second generation, and it is the thin end of a wedge: the moment the
assistant can reach somebody who is not looking at it, the question "what did
it do overnight" becomes askable, and the answer has to be "nothing" for the
permission model in `permissions.md` to hold.

The credit balance running low is the one genuine candidate, and it belongs to
the control plane, which knows about money, rather than to a tenant's alerts.
