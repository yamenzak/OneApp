"""The workspace assistant — a conversation that can look things up.

Not a second AI stack. It is one `@ai_feature`, calling the same gateway
everything else calls, holding and settling credits per turn, appearing in the
same settings page as a row with a model picker. What a chat needs that a
summary does not is a loop and a set of tools, and both of those live in
`onespace/ai/` beside the gateway rather than in here:

    ai/tools.py         a Python function described to a model as JSON Schema
    ai/transcript.py    one message shape, and the two provider shapes
    ai/conversation.py  ask, run what came back, ask again — within a budget

So this package is small on purpose:

    toolbox     what the assistant may read, all of it through existing endpoints
    context     where the question was asked from, and what that may narrow
    session     a conversation on disk, and as the transcript a provider is sent
    assistant   the declaration, the system prompt, and four endpoints

The two things worth knowing before changing any of it. **The tools run as the
person asking** — every one of them goes through the same `spaceview` and
`drive` calls the browser uses, so the assistant sees exactly what its asker
could have clicked to. And **every turn is a whole metered call**, so a question
that needs three lookups is charged as four; `max_turns` and `max_run_credits`
on the declaration are what stop that being open-ended.
"""

from . import context
from .assistant import SYSTEM, ask, forget, messages, send, sessions
from .session import MESSAGE, SESSION, WINDOW
from .toolbox import MAX_ROWS, MAX_TEXT, TOOLBOX, tools

__all__ = [
    "ask",
    "context",
    "forget",
    "MAX_ROWS",
    "MAX_TEXT",
    "MESSAGE",
    "messages",
    "send",
    "SESSION",
    "sessions",
    "SYSTEM",
    "tools",
    "TOOLBOX",
    "WINDOW",
]
