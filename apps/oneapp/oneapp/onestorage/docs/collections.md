# Collections

**A file is a Frappe `File`.** Not a row of ours pointing at one. That is the
first fact and almost everything else follows from it: there is no second store
anywhere in this product, so a record's attachment, a mail attachment, a
document, a workbook and a code file are all the same table.

## The four custom columns

The whole of the schema OneCloud adds to `File`:

    custom_kind         what it is — Document, Workbook, Code, Image, …
    custom_status       where it stands
    custom_trashed_on   when it was binned, which is what the sweep reads
    custom_opened       when this reader last opened it, behind Recents

## Owned

| Doctype | What it is |
| --- | --- |
| `File Version` | A file's history. `file`, `kind`, `title`, `manual`, `payload`, `byte_size`, `at_seq`, `saves`. One shape for a document's and a workbook's, which is `docs/WRITER.md`'s argument. |
| `File Link` | A link that outlives a session. `file`, `label`, `level`, `secret`, `expires_on`, `revoked`, `opened`, `last_opened`. |
| `Drive Access` | A WebDAV credential. `label`, `access_user`, `secret_hash`, `scope`, `folder`, `read_only`, `enabled`, `expires_on`, `last_used`. A secret hash, never a secret. |
| `Remote Folder` | A folder on somebody else's host. `folder_name`, `protocol`, `host`, `port`, `base_path`, `username`, `secret`, `private_key`, and the four fields recording whether it answered. |

## Borrowed

| Doctype | From | What it is here |
| --- | --- | --- |
| `File` | Frappe core | Everything. Overridden by `file.py` to move an upload to R2. |
| `DocShare` | Frappe core | Who a file is shared with. Not a table of ours. |
| `Comment` | Frappe core | The notes on a file — `chatting.py`. |
| `Doc Body`, `Sheet Book` | OneWriter, OneWorkbook | What a document's and a workbook's bytes are, for the two kinds that are edited rather than uploaded. |

## The three that are not tables, and are the design

**A folder is a `File` with `is_folder`,** parented by `File.folder` — what the
framework already does and the desk already uses.

**A place is a filter, not a table.** Home, Recents, Favourites, Shared, the
bin, Templates, Documents, Workbooks, Code: every one is the same query with a
different `where`, in `query.py`. That is why the rail is cheap and why a tenth
place would be a filter rather than a feature.

**The Records tree has no rows in its first two levels.** A directory per
record would be a `File` per record: renaming a record would become moving a
folder, deleting one a cascade. The doctype and record levels are made out of
the attachment rows at the moment somebody asks — `reading._records` for the
Drive and `scopes.children` for a mount, **one resolver**, so a rail place and
a WebDAV mount cannot disagree about what a record has on it.

## The sentence all three surfaces are built on

*A file attached to a record has `attached_to_doctype`; a file in a folder has
`folder`; a file can have both.* The Files tab, the Records tree and the Drive
are queries over one table rather than stores to keep in step.
