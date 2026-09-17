# Permissions

**OneWriter has no roles.** It is a service, so the answer to "who may open
this document" is OneCloud's, which is Frappe's: the `File` row's own
permissions, `is_private`, and `DocShare` for what has been shared.

A person who may read the file may open it; a person who may write it may save
it. There is no second check and there should not be, because a second check is
a place for the two to disagree.

## The one that is this module's own, and is subtle

**A record field in the prose carries its last answer.**

A token stores `source.field` *and* the value that was resolved when it was
last refreshed. So a reader with no permission on the bound record still sees a
document — the sentence reads, with the number in it — rather than a row of
blanks where the totals should be.

That is a deliberate leak and it is worth being clear about. The value in a
document is **what somebody who could read it put there**, frozen at that
moment, and the document was then shared with this reader. It is the same
disclosure as typing the number in, which is what people did before tokens
existed; what the token adds is that `refresh` asks again *as the refresher*,
so it never reveals more than that person can see.

`settle` is the end of it: a sent document stops asking, and the values in it
become a fact about a day.

## Sharing a document outward

`File Link` is OneCloud's, and the strong case is this module's reason for
existing: somebody mails a scope of works to a client who has never heard of
this workspace. The link carries a level, an expiry and a revoke, and the
export is a self-contained HTML file — so what lands in a stranger's inbox is a
document rather than a login.

## Plain-text files

`text.save_text` writes the object back under the same key, so the permission
question is exactly the `File`'s. `own_object` matters here for a reason that
is not a permission but behaves like one: every empty file starts as the same
single newline, so without it Frappe hands them all one object and the first
edit to any of them rewrites all of them — including somebody else's.

## What a model may do

Nothing, on its own. `intelligence.py`'s features produce text; the write is a
person pressing Apply or typing into the editor. `permissions.md` in `oneai/`
is the general rule.
