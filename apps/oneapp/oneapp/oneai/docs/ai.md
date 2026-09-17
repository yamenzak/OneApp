# AI

This is the module, so this page is the map of what it offers and what a
workspace may change about it. The mechanism is in `flows.md`.

## The five features declared here

| Key | Label | Capability |
| --- | --- | --- |
| `chat.workspace` | Workspace assistant | Text Generation |
| `text.summarise` | Summaries | Text Generation |
| `text.rewrite` | Writing help | Text Generation |
| `index.embed` | Search index | Text Embeddings |
| `ai.vision.read` | Reading pictures | Image Understanding |

`text.summarise` and `text.rewrite` are declared **once for the whole product**
and are what a composer, a document and a spreadsheet all reach for. That is
the point of the spine: six surfaces wanting the same six or seven things, and
one place they are declared.

`index.embed` is an `@ai_feature` like any other, deliberately. Retrieval is
not a special case with its own plumbing — it is declared, priced and switched
off the same way the writing verbs are. It was priced as a `Text Embeddings`
capability before anything used it, which is the order that stops a feature
arriving with no way to pay for it.

## What a tenant configures

All of it is `OneAI Settings` and its `features` table, and all of it is the
workspace owner's:

* **`ai_enabled`** — off stops every feature a workspace is allowed to stop.
  Critical features keep running: they are the process, not an assistant beside
  it.
* **Per feature**: `enabled`, `model_key` (picked from models that can do that
  capability), `model_options` (what else that model takes — resolved against
  the catalogue through `options.resolved`), and `prompt_addendum`, which is
  the customer's own wording appended to ours.
* **The assistant itself**: `assistant_name`, `assistant_avatar`,
  `assistant_tone` (a fixed vocabulary — Neutral, Friendly, Formal, Direct,
  Warm) and `assistant_personality` (free text).

Tone is a closed list and personality is not, and the split is on purpose: the
tone goes into the prompt as a word the model has to act on, and "how formal"
is a dial with a handful of stops. The specific goes in the free field.

Name and character are **workspace-level rather than per feature**, because a
person talking to it in the chat panel and a person reading something it
drafted are meeting the same character, and a name that changed between the two
would read as two products.

## What a tenant cannot configure

The system prompts. A feature's `system=` is ours, and a workspace adds to it
through `prompt_addendum` rather than replacing it. A prompt a customer could
replace is a prompt whose refusals a customer could remove.

## Where the money is

The control plane. `meter.py` holds and settles against a balance synced into
`credit_balance`; the catalogue and the prices are the operator's.
`docs/ONEADMIN.md` is that side.
