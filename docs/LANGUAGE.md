# How OneSpace speaks

Every word a customer reads is in this document's jurisdiction: a button, a
tab, an empty state, an error, a hint under a field, a toast. Not commit
messages, not code comments, not `docs/` — those are for us and can be as long
as the argument needs.

Two things are being enforced at once and they are easy to confuse. **Voice** is
what the sentence says and how. **Translation** is the machinery that says it in
Arabic and German. The first is a judgement a person makes; the second is a
lookup. Both are checked by `tests/test_language.py` and `tests/test_ui_copy.py`.

---

## 1. The voice

### Say the thing

> **Delete this file?** It will be in the bin for 30 days.

not

> **Are you sure?** You are about to permanently delete this item. This action
> cannot be undone. Please confirm that you wish to proceed.

The second sentence is longer, says less, and is wrong: it *can* be undone, for
thirty days. Length is not the rule — accuracy is, and accuracy is usually
shorter.

### A control is a verb, and it is the verb that happens

`Save`. `Send`. `Delete`. `Invite`. `Connect`. `Print`.

Not `Submit` for a thing that is not submitted, not `OK` for anything, not
`Confirm` where the real verb exists. The label and the outcome are the same
word: press `Publish` and a toast says `Published` — the same verb, in the past.

Where a button needs a noun, the noun is what it makes: `New format`,
`New letter head`, `Add an address`. Not `Create New Print Format Record`.

### Address the person, name the thing

"Your workspace", "your books", "the people you invited". The reader owns their
work; we do not narrate our own.

Never "the system", "the application", "the platform", "we were unable to". A
sentence about our plumbing is a sentence the reader cannot act on.

### One caveat, at the point of the decision

A hint belongs under the control it qualifies, and it is the *one* thing that
would change what somebody does:

> Turn off only once everyone can sign in another way, or nobody gets in.

Not three sentences of context, and not a link to documentation nobody has
written.

### Errors say what happened and what to do

> That address is already in this workspace.

> Mail is not set up for this workspace yet.

Not `Error: validation failed`, not an apology, not a traceback. If there is
nothing to do, say what is true — `Entries have been posted, so the chart of
accounts can no longer be replaced here.` — and who can help.

### Sentence case, everywhere

`New letter head`, not `New Letter Head`. Proper nouns keep their capitals.
A doctype's name is not a proper noun.

### Numbers and dates are the reader's

Never a raw id where a name exists. Never `2026-01-01T00:00:00` where
`1 January` will do. Never a byte count where `1.4 GB` will do.

### The words we do not use

`tests/test_ui_copy.py` holds the list and the replacement for each: doctype,
docname, fieldname, permlevel, enqueue, transaction, payload, hmac, manifest,
webhook, child table, whitelisted. And the vendors — Frappe, ERPNext, Stripe,
bench, press — which appear on an operator's screen, where they are the names
on our invoices, and nowhere a customer reads.

**We are not a Frappe reseller and this is not an ERPNext front end.** A
customer bought OneSpace. Where the framework's own wording leaks through — a
thrown message, a fieldtype's label, an app name in a picker — it is ours to
replace, not to pass on.

---

## 2. The machinery

Frappe 17 uses gettext, and **the msgid is the English sentence**. There is no
key to invent and no English file to maintain: `__("Delete")` is both the
source string and the lookup.

That is the whole reason to use their mechanism rather than a nicer one. Half
the sentences in this product — `Delete`, `Save`, `Search`, `Yesterday`,
`Sales Invoice` — are sentences Frappe and ERPNext have already translated into
forty languages, and using the same msgid means we get those for free and pay
only for what is ours.

### In the browser

```js
import { __ } from '@/shared/lib/runtime/translate'

__('Delete')
__('{0} files moved to the bin', [count])
__('Open', null, 'verb')          // where one English word is two elsewhere
```

`__(text, values, context)`, `{0}` and `{name}` placeholders, `msgid:context`.
The signature matches `frappe/public/js/frappe/translate.js` exactly, because
`bench generate-pot-file` reads `.vue` and `.js` looking for that function by
name — matching it is what makes extraction free.

Imported per file rather than a global, so a file that translates says so at
the top and the guard can tell.

### On the server

`frappe._("…")`, as it already is in 300-odd places.

### Where the translations live

`apps/oneapp/oneapp/locale/` — `main.pot` for the extract, `ar.po` and `de.po`
for the translations. `get_translations_from_apps` merges every installed app's
catalogue into one lookup, ours last, so a msgid Frappe already translates
resolves without our files being involved at all.

Three commands, and only the first needs a site:

```
scripts/dev.sh run scripts/i18n_pot.py   # re-extract every msgid
python3 scripts/i18n.py stat             # free / translated / owed
python3 scripts/i18n.py gap ar           # the sentences still owed
python3 scripts/i18n.py sync             # bring the .po files up to the POT
python3 scripts/i18n.py load DIR         # read translations back in, as TSV
```

`load` reads `english<TAB>arabic<TAB>german` files — the shape somebody who
translates for a living can be handed and can hand back without ever seeing a
`.po` file. A line whose English is no longer a msgid is reported rather than
dropped: it almost always means the wording moved after the file went out.

`sync` writes **only what is ours**: a msgid Frappe or ERPNext already
translates is left out, because carrying it would mean maintaining a second,
worse Arabic for `Save` that shadows theirs whenever ours loads last. It drops
those, drops msgids the extract no longer produces, and names each one it
dropped — a reworded sentence and a deleted one look identical from there, and
the difference is a translation somebody has to write again.

`bench compile-po-to-mo` compiles a `.po`; migrate does it too.

### One extractor row of our own

`apps/oneapp/babel_extractors.csv` claims `**/hooks.py` for the plain Python
extractor. Frappe's own map sends that file to the navbar extractor, which
resolves its real path and then asks for it relative to the bench — and our
apps are symlinked into the bench from this repository, so the subtraction
throws and the whole extract comes out empty, silently, with a zero exit. The
app's own map is read first, so one row is the whole fix.

### Who gets translated

The customer's app, and nothing else. `oneapp_control` is the operator console
and every reader of it works for us; `screens/ops/` is that same console
rendered inside the tenant SPA, so its strings land in `oneapp`'s POT beside
the customer's and are filtered out by where they came from. Bench groups,
shards and dunning ladders stay in English.

### What it costs a reader

Nothing, in English: the catalogue is not fetched, and every call returns its
own argument. In any other language it is one request, cached by the browser
for a year, awaited before the first paint — because a page that renders in
English and then repaints in Arabic has not flickered, it has changed
direction.

### Three languages, on purpose

English is the source. **Arabic** and **German** are the two we ship, because
they are the two our customers read. A fourth is a `.po` file and nothing else.

### What a deploy has to do

Nothing. `bench build` compiles every app's `.po` into
`sites/assets/locale/<lang>/LC_MESSAGES/<app>.mo`, which is where
`get_translations_from_apps` reads them, and Frappe Cloud runs `bench build` on
every deploy. The `.mo` is a build artifact and is not in this repository.

### The Arabic face

IBM Plex Sans Arabic, self-hosted, in three weights — and declared under
`InterVar`'s **own family name** with a `unicode-range` covering only the Arabic
block. `unicode-range` extends a family rather than replacing it, so every font
stack in the product, ours and frappe-ui's, picks up Arabic without a single one
of them being edited. The display face has the same arrangement with Reem Kufi.
Arabic sits optically smaller than Latin at the same size, so
`:root:lang(ar|fa|ur)` lifts the root to 106%.

Both faces are SIL Open Font Licence; the licence text ships beside the files in
`src/assets/fonts/`.

---

## 3. Right to left

`dir="rtl"` on `<html>`, set from the language before the app mounts, is most of
it: text, flex order, scroll direction and every logical property turn round on
their own. Three things it cannot do, and what we do instead.

**A class that names a side.** `ml-2` is two units on the *left* in every
language. Converted, and guarded — `tests/test_rtl.py` refuses a new one, and a
genuinely physical direction says `rtl-ok` on the line and why.

**A picture.** A chevron beside a collapsed section, an arrow that means Back:
frappe-ui draws a lucide icon as a CSS mask on a class named after it, so one
rule in `index.css` mirrors every cardinal one at once, and a new one is covered
the moment it is used. The diagonals are deliberately left alone —
`arrow-up-right` is the open-this-elsewhere mark, and it is also one of the
icons a customer can pick for a value of their own.

**A file that leaves.** The HTML export carries its own `lang` and `dir` and its
own right-to-left rules, written out physically rather than as
`padding-inline-start`, because it is opened by whatever the reader has.

### Two things the catalogue does not reach

**A date.** "8 days ago" is built by dayjs's `relativeTime` plugin out of a
locale of its own, so a page can be translated down to the last button and still
say the age of every row in English. `lib/runtime/dates.js` loads the one locale
the reader needs, beside `loadTranslations` and before the app mounts.

**A component's own words.** frappe-ui is a component library, not a translated
application, so a label it hardcodes cannot be reached — and
`SidebarCollapseToggle` hardcodes `Collapse`, on every screen with a sidebar.
`components/SidebarCollapse.vue` is that component with the label translated and
nothing else changed; it uses frappe-ui's own `SidebarItem` and its two exported
injection keys. Any other one that turns up gets the same treatment, and the
list is short.

### What is not right yet

Three surfaces draw themselves rather than being laid out, and none of them
turns round:

* the **spreadsheet grid**, whose columns run A, B, C from the left whichever
  way the page does;
* **charts** and the **Gantt**, whose axes and bars run the same way;
* the **quoted block in a reply**, which keeps a physical `border-left` on
  purpose — a mail client is not a browser, and logical properties are not
  something they can all be relied on to know.

And one word that is not a sentence: a file's **kind** — `Folder`, `Image`,
`Spreadsheet` — is a stored value the server sends, so it reads in English on an
Arabic file list. Translating it at the render site is the right fix and it is
the same fix as every other stored vocabulary in the product; it is worth doing
once, for all of them.

None of these makes a screen unusable in Arabic, and each is a day of its own.

---

## 4. What must never happen

* A string a customer can see that is not inside `__()` or `_()`.
* A sentence assembled from fragments — `__('Delete') + ' ' + name`, or one
  `__()` in a template followed by another that only reads as its second half —
  because word order is not the same in every language. Use a placeholder.
  `test_a_sentence_is_written_whole_and_not_glued_together` catches the shape
  it usually takes: a string that opens or closes on a dash or a comma.
* A translated string used as a key, a filter value, or anything compared with
  `===`.
* A `.po` entry for a msgid nothing produces any more.
* A physical direction in a class name — `ml-2`, `pr-3`, `text-left`,
  `border-l`, `left-0`. Use the logical property; see §3.
