# Flows

Server, in import order. A module may use the ones above it and never below.

    addresses    who may send as what, who may read what, what it signs with
    verify       sending as a domain the customer owns — and not until DNS says so
    connect      the mailbox somebody already had, over IMAP
    folders      the folders they had already sorted it into
    threading    which conversation a message belongs to
    linking      which records it is about, by rule
    concerns     which party and which person, from the addresses on it
    filing       which record it is about, when no rule can tell (a model ranks)
    inbound      what the Cloudflare Worker posts here
    outbound     rate limiting, which is the only part of sending that is ours
    suppression  bounces and complaints, and not sending there again
    rules        filing rules and the out-of-office
    people       a sender as a person rather than an address string
    faces        a picture for one, fetched once, served from here afterwards
    signatures   whose signature goes on, which is not Frappe's answer
    templates    a message written once and sent often
    intelligence what mail asks a model for

`mailbox/` is a package because reading mail is most of the screen:
`scope` → `flags` → `query` → `reading` → `filing` → `selections` → `sending`
→ `drafts` → `composing`.

## A message arriving

1. **Cloudflare's Worker posts it** to `inbound.receive`. `docs/EMAIL.md` is
   why that is the shape rather than an IMAP poll.
2. **`threading`** writes `custom_thread` — walking `in_reply_to` where the
   headers survived, falling back to the normalised subject where they did not.
3. **`linking`** applies the rules: which records this is about. Three of
   them, in order — the thread's own reference, an id this site issues written
   in the text, and then **`concerns`**, which reads the party and the person
   the addresses belong to. The order decides the primary reference: a message
   naming an invoice is about the invoice, and the customer it is also about
   is a second row.
4. **`filing`** is the fallback when no rule can tell. A model *ranks*
   candidates; see `ai.md`.
5. **`rules`** applies the workspace's own `Mail Rule` rows — folder, read,
   starred.

A mailbox somebody already had arrives the other way, over IMAP through
`connect.py`, and `folders.py` keeps the sorting they had already done.

## Reading — `mailbox/`

`reading.folders`, `reading.threads`, `reading.thread`. The flags —
`mark_read`, `mark_unread`, `star`, `unread` — are per person, on the `seen`
field this module added.

`selections.bulk` is the multi-row case; `filing.bin`, `filing.archive`,
`filing.add_folder`, `filing.drop_folder` are the moves.

## Writing

`composing.draft` opens one. `drafts.keep`, `drafts.kept`, `drafts.forget`
carry what was typed. `sending` sends, through `outbound`'s rate limit — the
only part of sending that is ours, because everything else is Cloudflare's.

**Closing the pane is not discarding.** What was typed is kept, so the control
says "Put it down" rather than drawing an ✕ that could mean either.

## Where the composer lives, and why it is two frames

The composer has two homes that want different frames, so the frame is a
component of its own (`ComposerFrame.vue`) and the composer knows nothing about
which one it is in.

**On a record's Mail tab, a dialog.** The tab is a few hundred pixels of what
was said; there is nowhere in that column to write without pushing the record
off screen.

**In OneMail, the reading pane** — the column a body is drawn in. A dialog
there covered the conversation with the reply to it, which is the one thing you
want in front of you while writing one. And since the desk, mail is often
itself a window over a record, so a dialog made three layers between the reply
and the thing it is about.

## Sending as the customer's own domain — `verify.py`

Not until DNS says so. The records are published, checked, and only then may a
workspace send as that domain.

## Bounces — `suppression.py`

A bounce or a complaint suppresses the address, and nothing sends there again
until somebody clears it.

## The page, in two places

`/one/mail`, and a desk window from the dock. Same two components either way —
a `windowed` prop only says the chrome belongs to the window.

What differs is **where mail keeps its place**: on the route it is the query
string, in a window it is the reactive `WHERE` in `lib/window.js`, because a
`router.push` from inside a window would navigate the page *behind* it.
`Mail.vue` reads `at` and emits `go`; `rowTo()` is where a thread row decides
between being a link and being a press.
