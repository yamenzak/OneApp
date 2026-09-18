# Notifications

One, and it is a letter rather than an alert.

**The invitation.** `invite._send` mails the link with `frappe.sendmail`,
queued — a form sent to forty people is forty SMTP round trips, and the person
who pressed the button should not be holding the page open for them.

Not through OneMail's composer. An invitation is a transactional message from
the workspace rather than a person's own mail, and putting it in somebody's
Sent folder would be filing a machine's letter as theirs.

**Nothing is sent when a form is answered**, and that is a gap rather than a
decision: a form is over a doctype, and what should happen when a record
arrives is `onespace/alerts.py`'s question — a workspace that wants to know can
write an alert on the doctype, which works today and reaches the right people
by role.

**A confirmation to whoever filled the form in**, where the form asks for one —
`custom_onespace_reply`, off by default. Sent to the address they gave, queued
through `frappe.sendmail`, best-effort. It says which form and that it arrived,
and deliberately not what they answered: a receipt listing what somebody just
told you in confidence is that confidence sent unencrypted to whatever mailbox
they gave. See `invite.confirm`.
