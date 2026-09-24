# OneMail

Mail is gone from here: it was rebuilt on the desk in OneDesk's `one_mail`, and the mailbox, the composer, the record's Mail tab and the Cloudflare worker went with it.
What remains is the `Correspondence` doctype — a formal letter as a record, which RUA's space manifest (`oneapp_control/spaces/rua.py`) puts a screen on.
It stays in the `OneMail` module because a doctype's module is where Frappe loads its controller from, and moving it would be a migration for no gain.
