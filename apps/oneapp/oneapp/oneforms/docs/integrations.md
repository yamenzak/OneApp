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

**`www/one.py`**, which is the one place outside this module that had to
change. `/one/...` redirects a guest to a sign-in page, and two paths must not:
a shared file and a public form. `OPEN_PREFIXES` is both, named rather than
inferred, and `tests/test_link_editing.py` reads it back.

**OneAI**, through `ai_actions` and `onespace_chat_tools` — two kinds and three
tools, all of which end at this module's own service calls. `docs/ai.md`.

**OneCode**, for the stylesheet: `CodeDialog` is the same editor the Drive opens
a `.py` in, opened over `custom_css` from the builder's Style button. A second
code box in this product would be a second set of keybindings for one job.

**Mail**, through `frappe.sendmail` and not OneMail's composer — an invitation
is a letter from the workspace rather than a person's own.

**Not ERPNext, not HRMS.** A form is over whatever the workspace has, and a
site without either still has forms.
