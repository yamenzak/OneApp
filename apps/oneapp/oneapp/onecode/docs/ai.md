# AI

**OneCode declares no `@ai_feature` of its own.** What a person gets while
editing code here is OneAI's, reached the way every other surface reaches it.

## What works today

**The writing verbs.** `oneai/text.py` declares them once for the whole
product — summarise, improve, proofread, change tone, write this — and the
editor chrome offers them because it is the shared chrome. They are a text
feature and a code file is text.

**The file verbs.** Making a file, renaming one, moving one: `oneai/kinds.py`
holds the suggestion kinds for the framework's own nouns, and a file is one.

**The chat.** `oneai/chat/toolbox.py` can read the Drive, and a code file is a
file in it.

## What a tenant configures

Nothing here. Every dial is OneAI's: `oneai/settings.py` holds the workspace's
model choice, its per-feature switches, its ceiling and the assistant's own
character, and there is no OneCode row in that list to set. A workspace that
switches text generation off loses the verbs in this editor along with every
other editor, which is the correct blast radius for one switch.

## What is not built, and is the interesting one

**A project-scoped index.** `oneai/index.py` embeds a record and scans over the
embeddings, and it already scopes per record. A project is a folder and a
folder is a scope, so "which file in this project does X" is the retrieval
question this module will ask and does not yet. It is item 4 in the README's
closing list, and it waits on serving for the same reason the rest does: a
project nobody can run is a project nobody has enough of to search.
