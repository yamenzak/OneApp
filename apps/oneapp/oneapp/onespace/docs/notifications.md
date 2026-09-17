# Notifications

**The engine owns the notification machinery and ships almost no rules.** Two
files, and the split between them is the point.

## `notifications.py` — the feed

Every in-app row a person has, across every space, with the read state and the
switches. It is the spine a space's rules land on, and it is why a rule is
typed `Alert` rather than sent as mail.

## `alerts.py` — what a rule may say, and to whom

`addressable(doctype, fieldname)` is the function that decides whether a field
can receive a notification. It refuses a Link to `Employee` and **says so in
its own docstring**, because `HR-EMP-00003` is not an address.

What it accepts is `owner`, a Link to `User`, or a role. That refusal is what
made OnePeople's `custom_person` necessary — `collections.md` there has the
story — and the whole class of "tell the person this is about" opened with no
engine change once a Link to User existed on the row.

`alerts.save` is the door a workspace's own rules go through, and also the door
a space's shipped rules go through. **They arrive as the workspace's own**:
listed, editable, pausable and deletable in Settings like anything somebody
typed there.

`alerts.roles` narrows a rule's recipients to the roles this workspace actually
holds, read off `OneSpace Site State.roles_json` — which is why a dev site with
an empty `roles_json` refuses every rule addressed to a role.

## `routing.py` — a handover, not a notice

"When a task reaches In review, hand it to the reviewers" is Frappe's
`Assignment Rule` wearing the sentence somebody would say. It shares a gate and
a vocabulary with the alerts panel.

The condition is **compiled from three controls rather than typed**, because
`assign_condition` is evaluated on every save of every record of that kind.

**Unassigning is deliberately not offered.** Work vanishing from somebody's
list weeks later, with nothing on the record to say why, is a footgun with a
delay on it.

## Three decisions that apply to every rule in the product

**`created`, not `submitted`.** For request-shaped doctypes, the draft *is* the
request — HRMS refuses to submit a Leave Application until it is already
approved, so a rule on Submit would tell the approver about a decision they had
already made.

**In-app, not email.** Frappe sends both from inside one `try`, so on a
workspace with no outgoing email account the failed send takes the in-app row
down with it — logged where nobody looks. Turning email on is one control in
Settings, belonging to a workspace that has configured mail.

**Seeded once, keyed on the subject.** A rule somebody reworded stays reworded
and one they deleted stays deleted. Reapplying every fifteen minutes would undo
an afternoon's work with nothing to say why.

## What the engine itself sends

Almost nothing. The expiry sweep (`expiry.py`) is the one genuine engine-owned
notice, and it is about a `Compliance Document` a workspace has to hold.
Everything else belongs to a space, because the space owns the screen somebody
would act on.
