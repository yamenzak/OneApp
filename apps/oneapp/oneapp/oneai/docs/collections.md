# Collections

## Owned

| Doctype | What it is |
| --- | --- |
| `OneAI Settings` (single) | The workspace's AI switch and everything about its assistant. `ai_enabled`, `credit_balance`, `last_sync`, `assistant_name`, `assistant_avatar`, `assistant_tone`, `assistant_personality`, `features` (a table), plus `catalogue_json` and `registry_json` cached from the control plane. |
| `OneAI Feature Setting` (child) | One row per feature: `feature_key`, `enabled`, `model_key`, `model_options`, `prompt_addendum`. The workspace's answers about one thing a model is asked to do. |
| `OneAI Chat Session` | A conversation. `title`, `last_message_on`, `message_count`, `credits`, `archived`. |
| `OneAI Chat Message` | A turn. `session`, `seq`, `role`, `credits`, `stopped`, `content`, and the three tool-call fields. |
| `OneAI Suggestion` | Something a model asked for and did not do. `kind`, `summary`, `state`, `about_doctype`/`about_name`, `payload`, `before`, and where it was applied. |
| `OneAI Embedding` | What a record is about, as a direction. `reference_doctype`, `reference_name`, `title`, `model_key`, `dims`, `digest`, `vector`. |
| `OneAI Written Value` | A value a model wrote. `reference_doctype`, `reference_name`, `fieldname`, `feature_key`, `model_key`, `asked_by`. |

## Two of them are the arguments worth reading

**`OneAI Suggestion` exists because a model cannot write.** It is the record of
what *would* change — this record, these fields, that value — held between the
asking and the doing, and the doing is a request a person makes by pressing
Apply. `before` is what the record said at the time, so an Apply against a
record that moved underneath can be refused rather than silently overwriting.

It used to be a `Chat Change` under the chat, and it is not any more because
mail and the editors offer cards too: a suggestion belongs to no module, so it
sits in the spine.

**`OneAI Written Value` is a row per `doctype`/`docname`/`fieldname` and not a
field on the record**, because a workspace's documents belong to apps we do not
own and we do not add a column to somebody else's schema to mark a value. It is
what puts the sparkle beside a field's label, and it is hooked on
`doc_events["*"]` so a person rewriting a value takes the mark off it.

## Borrowed

| Doctype | From | What it is here |
| --- | --- | --- |
| `File` | Frappe core, via OneCloud | What `vision.read` reads, and what a written document lands in. |
| *Anything* | Everywhere | `index.embed` and the suggestion kinds are declared over the framework's nouns rather than over a list. `doc_events["*"]` is the hook. |

## The catalogue, which is not ours

`catalogue_json` and `registry_json` are **cached from the control plane**
rather than fetched per request. Choosing a model must work while the control
plane is unreachable, and pricing a call must not depend on a network hop in
the middle of one. The models themselves — `AI Model`, `AI Model Price`,
`AI Feature`, `AI Usage Record` — are control-plane doctypes and live in
`oneapp_control`.
