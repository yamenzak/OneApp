# Integrations

## Frappe — deeply, and on purpose

**`File` is overridden** (`file.py`) rather than wrapped: the same row an
attachment is, with the object moved to R2 and the URL rewritten.
`set_folder_name` is the other half — it leaves attachments folderless, so
Frappe's `Home/Attachments` bucket never fills.

**`DocShare`** is sharing with a person. **`Comment`** is a note on a file.
Neither is a table of ours, and both are that way for the same reason: two
systems deciding one question is two systems that will disagree.

## ERPNext and HRMS

**Nothing directly, and everything indirectly.** A quotation's attachments, an
employee's documents and a project's drawings are `File` rows with
`attached_to_doctype` set, so they are in the Drive without either app knowing
this module exists. The Records tree is that fact rendered.

## Cloudflare R2

Where the bytes are. `r2.py` holds the client and the presigning;
`r2.public_url` is what serves an asset. The region is the customer's choice,
and `onestorage/legal.py` says so in the subprocessor list and the privacy
policy.

## OneWriter, OneWorkbook, OneCode

**They are this module, landed on a place.** A document is a `File` and a
workbook is a `File`, so OneWriter is not a second application over a second
store — it is the Drive on `place=documents`, OneWorkbook on `workbooks`,
OneCode on `code`. Each has its own dock tile, its own mark colour and its own
corner; `lib/window.js` holds the list.

`kinds.py` is what decides which editor opens, and it matches Code **last**, so
`.md` and `.txt` are Documents. `onecode/languages.is_code` is the one call
across that seam.

`File Version` is shared by all three, which is `docs/WRITER.md`'s argument: a
version of a workbook and a version of a document are one doctype.

## Mail

The owner's face on a file row comes from `people.py`, which was mail's sender
resolver until mail left for OneDesk's `one_mail`; the file list was its last
reader.

## The engine (`onespace`)

* **The record shell** — a record's Files tab opens the OneCloud window over
  that record's attachments, through `linked.py`.
* **The desk** — OneCloud is a window (`docs/DESKTOP.md` stage 6), because a
  file manager is the thing people keep open beside what they are doing. Its
  route stays as the maximised case so a deep link still works.
* **Two OneCloud windows cascade** rather than share a corner: two folders open
  at once is the reason file managers have windows at all, and dragging between
  them is the gesture.
* **Quota** — `quota.py` and `limits.py` read what the plan allows, which the
  control plane decides.

## OneLegal

`legal.py` carries R2 as a subprocessor, the region, and the retention the bin
implies. A new bucket region is a line here and a new document hash.

## Outward: WebDAV

`dav.py` serves the Drive to Finder, to VS Code, to anything that speaks it.
`Drive Access` is the credential and `scopes.py` decides what a mount can see —
the same resolver the Records tree uses, so a mount and a rail place cannot
disagree.

## OneAI

See `ai.md`.
