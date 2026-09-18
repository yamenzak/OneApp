# Integrations

**Frappe.** `Web Form`, `Web Form Field` and `Web Form Request`, which are the
whole of what this module is over. Nothing here re-implements a part of them:
the public endpoints (`accept`, `get_form_data`, `get_web_form_list`, `delete`)
are Frappe's, all `allow_guest=True` and all rate-limited, and the security
around a key is Frappe's too.

**The engine.** `onespace/finding.placed` says which doctypes this reader can
make a form over. That is the one seam that matters, and it is deliberately the
same call the finder searches with and the approvals inbox places rows with:
three readings of "which doctypes are yours" would disagree the first time a
manifest moved a screen.

**`onespace/workspace`** for `OWNER_ROLE` and `SUPPORT_ROLE` — who may make a
form at all.

**Every space, indirectly and by design.** A form over `Job Applicant` feeds
OnePeople's hiring screens; one over `Lead` feeds OneCRM. This module knows
none of their names and needs to know none.

**Not ERPNext, not HRMS.** A form is over whatever the workspace has, and a
site without either still has forms.
