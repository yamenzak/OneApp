# Collections

**The sales schema is ERPNext's.** What this module owns is the four things a
desk needs that ERPNext has no noun for.

## Owned

| Doctype | Child of | What it is |
| --- | --- | --- |
| `One Deal Stage` | — | A pipeline column a workspace owns. `stage_name`, `category`, `probability`, `colour`, `position`, `description`. |
| `One Stage Change` | `custom_stage_log` | Where a deal or a lead has been. `stage` (**Data**, not Link), `entered_on`, `left_on`, `days`, `moved_by`. |
| `One Call` | — | A call that happened. `naming_series`, `with_whom`, `way`, `number`, `contact`, `at`, `minutes`, `outcome`, `person`, `about_doctype`/`about_name`, `note`. |
| `One Response Target` | — | An SLA. `target_name`, `enabled`, `applies_to`, `position`, `priority_field`, `applies_when`, `holiday_list`, `week`, `levels`, `rolling`, `resolved_when`. |
| `One Response Level` | `levels` | What is promised at one priority. `level`, `is_default`, `respond_within`, `resolve_within`, `position`. |
| `One Response Rule` | `applies_when`, `resolved_when` | One condition. `fieldname`, `operator`, `value`. |
| `One Working Day` | `week` | One day of the working week. `day`, `works`, `from_time`, `to_time`. |

## Two of them are worth the detail

**`One Stage Change.stage` is `Data`, deliberately.** It was a Link to `One
Deal Stage` and a lead's `In Process` raised `LinkValidationError` — but the
real argument is bigger than that bug: a log records what a value *was*, and a
Link that can be renamed or deleted makes history mutable.

Capped at 100 rows (`progress.MOST`). A deal that has been round the houses two
hundred times is a deal whose first fifty moves nobody will read.

**`One Response Target.position` is written from the declared order**, by
`answering.ensure`. Every target seeded at position 0 sorted by name instead,
so "Answer a lead" beat "Answer a web lead" and the narrow target could never
win. Found by reading rows back on a dev site, not by a test.

## Borrowed

| Doctype | From | What it is here |
| --- | --- | --- |
| `Lead` | ERPNext | Subclassed as `onecrm.lead.Lead`. `qualification_status` is the stage field. |
| `Opportunity` | ERPNext | The deal. Subclassed as `onecrm.deal.Deal`. |
| `Quotation` | ERPNext | What a deal becomes on paper. |
| `Customer`, `Prospect`, `Contact`, `Address` | ERPNext | The party, and how to reach them. |
| `Communication` | Frappe core, via OneMail | What stops the answering clock. |
| `Contract`, `Contract Template` | ERPNext | Underneath a won deal. |
| `Sales Stage`, `Opportunity Type`, `Opportunity Lost Reason`, `Territory`, `Customer Group`, `Market Segment`, `Campaign`, the UTM tables | ERPNext | The masters a pipeline is measured by. |
| `OneSpace Word` | The engine | The workspace's own word for a screen — Deals as *Donations*. |
| `OneSpace Saved View` | The engine | A rep's own filters. |

## The custom fields

Declared in `oneapp_control/spaces/onecrm.py`, because a custom field belongs
to the space that renders it. The answering set is the large one:

    custom_respond_by / custom_answered_on / custom_answering
    custom_settle_by  / custom_settled_on  / custom_settling
    custom_response_target / custom_response_level
    custom_answered_in / custom_settled_in
    custom_rounds / custom_round_began

plus `custom_stage_log`, `custom_stage_since` and `custom_weighted_amount`.

**Custom fields are applied by the seeder rather than by migrate**, which is
why every controller here guards on `meta.has_field` before touching one.
