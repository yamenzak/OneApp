# File-type icons

Taken from [frappe/suite](https://github.com/frappe/suite) at
`suite/public/drive/images/icons/`, commit `95c38bf`.

Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
Licensed under the GNU Affero General Public License v3, the same licence this
repository carries. They must not be moved to a permissive licence.

**They are renamed to the kind they draw**, not to the thing Frappe called
them, because `lib/art.js` keys off the filename and the key that matters here
is `custom_kind` — `onestorage/kinds.py` is the closed set of ten and this
directory is the same ten plus one. The two renames worth writing down:

* `Document.svg` is Frappe's `word.svg` and `Doc.svg` is their `document.svg`.
  Our `Document` is an uploaded `.docx`; our `Doc` is a document somebody wrote
  here. `kinds.py` explains why those are two kinds and not one, and the icons
  follow the same split — a Word file looks like a Word file.
* `Folder-shared.svg` is their `shared-folder.svg`, which is the one icon here
  that is not a kind: a folder somebody else owns, in the Shared place.

Why theirs rather than lucide, which is already in the bundle: a file manager's
grid is a wall of icons, and ten grey outline glyphs at 16px are ten things a
reader has to *read*. These are the coloured, filled, per-format marks every
file manager has had for thirty years, and they are recognised rather than
read. It is the single largest visual difference between this Drive and one
people already know how to use, and it costs 9.8 kB.

## The two that are ours

`Folder.svg` and `Folder-shared.svg` are drawn here rather than taken. Frappe's
were a single flat `#525252` silhouette with square corners, drawn for a card
and used by us at sixteen pixels in a list — where a folder is most of what a
list *is*. At that size a dark grey rectangle with a notch in its top edge is a
dark grey rectangle, and a list of twelve folders read as a column of black
boxes. It was the first thing anybody said about this screen.

So: two tones and a radius. An amber folder is what a folder looks like in
Windows and on a Mac, which is the whole argument — this is a mark to be
recognised and not read, and the recognition is thirty years old. The shared
one is the same shape in the blue every product uses for "somebody else's",
with a person on it, so the two are told apart by colour before they are told
apart by the figure.

They are ours, so they carry no obligation. Everything else in this directory
is Frappe's and does.
