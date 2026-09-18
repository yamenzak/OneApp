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
