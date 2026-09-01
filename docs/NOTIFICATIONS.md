# Notifications

An audit of what Frappe Framework actually ships — read off `frappe` at
`17.0.0-dev` on the development bench, not from memory — and what OneApp does
with it.

The short version: **the framework already writes our notifications and nothing
renders them.** Assignment and @mention both produce rows today, on every
tenant, and no surface in OneSpace has ever shown one. Most of this document is
about how little we have to build, and about the one place where the framework
hands us a decision rather than an implementation.

---

## 1. Five things are called "notifications"

They are unrelated, and conflating them is how this gets designed badly.

| # | What | Where | Is it for us |
|---|------|-------|--------------|
| 1 | **Notification Log** — the per-user feed: mentions, assignments, shares, alerts | `frappe/desk/doctype/notification_log/` | **Yes.** This is the feed. |
| 2 | **Notification (the rule)** — "when a Sales Order is submitted, email/Slack/notify" | `frappe/email/doctype/notification/` | **Later.** A real feature, and a big surface. |
| 3 | **Desk sidebar counts** — open-document counts per doctype, the numbers beside desk links | `frappe/desk/notifications.py::get_notifications` | **No.** A desk artefact; our screens already carry their own counts. |
| 4 | **Push** — a thin client for an external relay that talks to FCM | `frappe/push_notification.py` | **Yes, eventually**, and it is the one real decision. |
| 5 | **Email Digest** — a scheduled roll-up email | `frappe/email/doctype/email_digest/` | **No.** Nobody asked, and a digest of a feed nobody reads is worse than nothing. |

Also nearby and deliberately not in this list: `frappe.publish_realtime`, which
is transport rather than a notification, and which OneSpace already uses for the
list following the site and for presence on a record.

---

## 2. Notification Log, as it stands in v17

Recently reworked — `Notification Type` and `Notification Type Preference` are
dated 2026 and there are v16 backfill patches — so this is *not* the shape most
apps in the wild are written against.

**The record.** One row per recipient per event. Its fields split cleanly in
three:

* *the notification* — `type` (a **Link** to `Notification Type`, extensible),
  `title`, `description`;
* *the reference* — `document_type` / `document_name`, `source_doctype` /
  `source_name` (the thing the mention was written *in*, e.g. the Comment),
  `link` (a plain URL), and `app`;
* *the email of it* — `subject`, `email_content`, `email_header`.

`before_insert` mirrors the two pairs, so a producer that sets either gets the
other. Set both to make the email differ from the in-app text.

**`app`** is new and is the closest thing the framework has to our Space: it
scopes an app-specific notification panel, and is derived from the reference
doctype's module → app when the producer does not set it.

**Fan-out happens on write.** `enqueue_create_notification(users, doc)` enqueues
`make_notification_logs`, which writes one row per enabled user, skipping the
actor unless the type is in the `notification_self_notify_types` hook. Optional
`dedupe_on=[...]` skips a row that already exists on the same field values.

**Delivery is two channels, decided per row on insert:**

* `frappe.publish_realtime("notification", user=...)` — **a poke with no
  payload.** The client refetches. Worth copying: it means nothing sensitive
  rides the socket and there is no second serialisation to keep in step.
* email, when `is_email_notifications_enabled_for_type(user, type)`.

**Reading** is `get_notification_logs(limit)`, `mark_as_read`,
`mark_all_as_read`, all whitelisted, with a permission query condition pinning
every read to `for_user = session.user`. `clear_old_logs(days=180)` runs from
the daily hooks.

### Preferences

`Notification Settings`, one per user, created with the user.

* `enabled` — everything off, checked in `_get_user_ids` before a row is even
  written.
* `enable_email_notifications` — the master email switch.
* `email_notification_types` — a child table of `Notification Type`, and it is
  an **allow-list**: a type is emailed only if the row is there. An empty table
  means "email me for nothing". New users are seeded with every enabled
  non-skip type, so empty is always a choice and never a missed migration.
* per-feature checkboxes for things that have no in-app notification at all
  (event reminders, thread mail on assigned documents) — read through
  `is_email_enabled_for_feature`, not the allow-list.

### Extension points

Three, all honest:

* `Notification Type` — a doctype. Built-ins (`Mention`, `Energy Point`,
  `Assignment`, `Share`, `Alert`) are seeded in code on `after_install` /
  `after_migrate` and protected from deletion.
* `notification_skip_email_types` (hook) — types whose log never emails, because
  something else owns the email. Framework ships `["Alert"]`.
* `notification_self_notify_types` (hook) — types delivered to the actor too.
  Framework ships `["Alert"]`.

### Who produces one, in the framework

`assign_to.add` (Assignment) · `notify_mentions`, called from
`Comment.after_insert` (Mention) · `frappe.share.add` (Share) · the Notification
rule with **Send System Notification** ticked (Alert) · Email Account failures ·
Submission Queue.

---

## 3. Push, and what the framework does *not* do

`frappe/push_notification.py` is ~290 lines and is a **client for a service
Frappe runs**, not an implementation:

* it POSTs to `notification_relay.api.*` on a server named by the site config
  key `push_relay_server_url`;
* `Push Notification Settings` (Single) holds `enable_push_notification_relay`
  and an api key/secret the site *registers for itself* — it generates a token,
  caches it, and exposes `auth_webhook` for the relay to call back and verify
  the site owns the domain;
* the API is `add_token` / `remove_token` per user, `add_topic` /
  `subscribe_topic`, and `send_notification_to_user` / `..._to_topic` with
  title, body (≤1000 chars, HTML stripped), and `data.click_action` for the
  link;
* every call carries a `project_name` the relay must already know.

**Three things follow, and they are the whole decision:**

1. **The browser half does not exist.** `subscribe(fcm_token, project_name)`
   takes a token that something else had to obtain. That something is the
   Firebase web SDK plus a service worker — neither is in the framework, and
   frappe-ui (checked at `1.0.0-beta.55`) ships nothing for it either.
2. **It is FCM, through Frappe's relay.** Notification titles and bodies for our
   customers' records would transit a third party's service and Google's. We
   already tell customers they may pin storage to an EU jurisdiction
   (DECISIONS §5); "except the notification text" is a sentence we would have
   to write.
3. **`project_name` is not ours to choose** unilaterally — the relay operator
   has to know it.

None of that makes the relay wrong. It makes it a decision rather than a
default, and it is the only part of this audit that is not simply "adopt".

---

## 4. What OneApp has today

* **Toasts** (`lib/notify.js`) — the outcome of the thing you just did. Not
  notifications; a notification is about something you were not watching.
* **Realtime** — `lib/socket.js`, the list following `list_update`, presence on
  an open record.
* **Transactional email** — `oneapp_control/notifications/emails.py` for signup
  and lifecycle, sent from the control plane; `oneapp_core/email/outbound.py`
  for the tenant's own mail through Cloudflare's SMTP.
* **A pull channel from the control plane** — `sync.sync_from_control_plane()`,
  every fifteen minutes and callable on demand.
* **No feed at all.**

And the finding that decides the shape of Phase 1:

> **Assignment and @mention already write Notification Logs on every tenant.**
> `spaceview.assign()` calls `frappe.desk.form.assign_to.add`, which notifies;
> `spaceview.comment()` inserts a `Comment`, whose `after_insert` calls
> `notify_mentions`. Both have been producing rows since the day they shipped.
> There is nowhere in OneSpace to see one.

---

## 5. How OneApp adapts it

### Decision 1 — the feed is Notification Log, not a doctype of ours

Frappe's own control plane went the other way (`Team Notification`, a per-team
row with capability gating) and it was right *for them*: their audience is a
team, and their control plane has no per-user rows to fan out to. Our tenant
side is neither. It is a Frappe site with real Users, and the framework's
notification is already per-user, already permissioned to `for_user`, already
swept at 180 days, already emailed by preference, already deduped, and already
being written by two of our own features.

Writing our own would mean re-implementing all of that in order to *stop*
receiving the notifications we already get.

### Decision 2 — a notification's route is derived, not stored

`Notification Log.app` cannot carry a Space: a Space is a manifest over
doctypes, not a Frappe app, and one doctype may be granted to several Spaces.

So OneSpace resolves the destination at read time, from `document_type`, through
the manifest it already has — the same derivation the rest of the product uses.
`/one/space/<code>?screen=<screen>&record=<name>`, picking a Space this reader
may actually open, and falling back to the row's own `link` when the producer
set one. A notification that cannot be resolved to a screen is still shown; it
just does not link anywhere, which is the truthful rendering.

### Decision 3 — our types are registry rows, not a fork

`Mention`, `Assignment`, `Share` are ours already. `Energy Point` gets disabled
rather than deleted (the framework protects built-ins, and disabling is the
supported gesture). We add:

* **`Workspace`** — lifecycle and billing: over quota, dunning, a restore
  finished, a plan changed. Written on the tenant by the control-plane pull.
* **`Action`** — a declared screen action that ran long and finished.

Both go in `notification_skip_email_types` where the control plane already sends
the email, so a customer is not told twice about a failed payment.

### Decision 4 — the control plane does not write into tenants; the tenant pulls

We already have exactly one authenticated channel between the two, and it runs
every fifteen minutes. Workspace notices ride it: the control plane keeps a
small queue per tenant, `sync_from_control_plane` drains it and materialises
each into a Notification Log on the tenant, keyed so a re-drain cannot duplicate
(`dedupe_on` is in the framework for this). No new transport, no inbound
credentials on a tenant site, and the feed the reader looks at is one feed.

The cost is honest and worth stating: a billing notice can be up to fifteen
minutes late in-app. The email is immediate, and for the events that matter the
email is the primary channel anyway.

### Decision 5 — push is a seam before it is a feature

The framework's `PushNotification` is small enough to sit behind our own
`push.send(user, title, body, link)`. Behind that seam:

* **Phase 1 (recommended first):** nothing. In-app plus email covers the whole
  feed, costs no third party, and is available the day the panel ships.
* **Phase 2 (recommended):** **Web Push with VAPID keys we own.** Standard,
  no FCM project, no relay, no `project_name` to negotiate, and the content
  never leaves our infrastructure — which keeps the EU-jurisdiction promise
  intact. Chrome, Firefox and Edge everywhere; Safari and iOS 16.4+ once the
  workspace is installed as a PWA, which is a real limitation and belongs in
  the copy beside the toggle rather than in a footnote.
* **Fallback, behind the same seam:** Frappe's relay, if we ever ship a native
  mobile app — where FCM and APNs are unavoidable and the relay stops being a
  dependency we chose and becomes the cheapest way to have one.

**This is the one open question in this document**, and it is a product
question rather than an engineering one: *may a customer's notification text
transit Frappe's relay and Google's FCM?* If yes, the relay is less work. If no
— which is the answer our own jurisdiction promise implies — Phase 2 is Web
Push and the relay never ships.

### Decision 6 — what we are not building

* **The desk's open-document counts.** Our screens carry their own count and
  their own favourites; a second, differently-computed number beside a nav item
  is the desk's answer to a problem we do not have.
* **Email Digest.** Not until somebody asks.
* **The Notification *rule* doctype as a customer surface.** It is a real
  feature — "email me when an invoice is overdue" — and it is a screen with a
  Jinja editor, a condition editor and a channel picker. It is its own project,
  and the feed has to exist first.

---

## 6. The shape of the work, in order

1. ~~**Render what already exists.**~~ **Done.** `oneapp_core/notifications.py`
   reads the feed; `NotificationList` draws it; the bell sits in the rail's
   foot and the More sheet carries it on a phone. Assignment and mention lit up
   with no producer written, which was the whole bet.
2. ~~**Route a notification to a screen.**~~ **Done**, and derived — see
   Decision 2.
3. ~~**Preferences.**~~ **Done**, and on the *account* page rather than in
   workspace settings: it is a person's own answer, and half a workspace cannot
   open the settings dialog at all. Two switches and a list, which is the whole
   of Frappe's model — everything off, email off, and per type whether email is
   wanted. The list is drawn as switches because the framework treats an empty
   table as "email me about nothing", and an empty picker reads as "not set up
   yet", which is the opposite.
4. ~~**`Workspace` notices over the existing pull.**~~ **Done.** The control
   plane answers a sync with the lifecycle events this workspace has not been
   told about; the tenant writes each one into the framework's own Notification
   Log, to whoever holds the owner role, and advances a watermark. Ten wordings
   for the ten events a customer can act on, out of the sixteen recorded.
5. **Push behind the seam** — Decision 5. Deliberately not built: see below.

### On push, and why the arc closes without it

`Push Notification Settings` and `frappe.push_notification` are the framework's,
and they are a client for a relay Frappe runs that talks to Google's FCM. Our
own EU-jurisdiction promise (DECISIONS §5) says a customer's data can be pinned
to a jurisdiction; "except the text of every notification" is not a sentence we
want to write, and the browser half does not exist in the framework or in
frappe-ui anyway.

So push waits for Web Push with keys we own, and the arc is closed without a
seam standing empty. **Nothing has to change for it to arrive**, which is the
point of having used the framework's store: a push notification carries the
same title, body and link a Notification Log row already holds, and a producer
is where it would be sent from. The work is a service worker, a subscription
per browser, and a sender — not a data model.

## 8. Where each piece lives

| | |
|---|---|
| The store, per user | `Notification Log` (framework) |
| Types | `Notification Type` (framework) + `Workspace` (`notifications.install_types`) |
| Preferences | `Notification Settings` (framework), read/written by `notifications.preferences` |
| Which types email | the allow-list, plus `notification_skip_email_types` in `oneapp/hooks.py` |
| Producers | `assign_to.add`, `notify_mentions`, `frappe.share.add` (all framework), and `sync.sync_notices` |
| The feed, shaped | `oneapp_core/notifications.py` |
| Where a row goes | `notifications._routes`, derived from the manifest |
| The panel | `NotificationBell` (rail) · `NotificationList` (both) · a Dialog on a phone |
| The count | `lib/notifications.js`, following the framework's `notification` event |
| Preferences UI | `NotificationSettings.vue`, on the account page |
| Notices, control-plane end | `api/tenant.NOTICES` and `_notices` |
| Notices, tenant end | `sync.sync_notices`, watermarked by `OneSpace Site State.last_notice` |

## 7. Three things building step 1 turned up

**Nobody but the Administrator was assignable.** `assignees()` copied Frappe's
own filter, `user_type = "System User"`. On a desk site that separates a
colleague from a portal customer. Here it separates nobody from everybody: our
roles are created with `desk_access` off — that is what keeps a workspace out
of `/app` (DECISIONS §7) — and Frappe recomputes `user_type` from exactly that
flag, so **every member of every workspace is a Website User by design**. The
picker had therefore offered the site admin and nobody else, on every real
workspace, for as long as assignment has existed. It asks the question this
product's own way now: who holds a role we granted.

**Assigning to `Administrator` notifies nobody, on any Frappe site.**
`_get_user_ids` filters recipients on `User.email`, and the Administrator's
email is `admin@example.com` rather than `Administrator`. Every ordinary user
has name == email and works. Not ours to fix, and worth knowing before an hour
goes into it.

**A notification is enqueued, so a bench with no worker writes none.** See
DEVLOOP — `scripts/dev.sh worker` exists now, and the spec's failure message
names it.

**Recipients are emails, not names.** `enqueue_create_notification` documents
"user emails" and means it — it resolves them with `User.email in (...)`. For an
ordinary account the two are the same string, which is why the distinction
looks like nothing until the recipient is the Administrator. Then the notice is
enqueued, the job succeeds, and nothing is written. `sync._owners` plucks
`email` for exactly this reason.

One thing we accept rather than fix: the framework's producers write their
sentence with markup in it (`<b class="subject-title">` around the record's
title), and a panel row strips it. The desk shows the same sentence with the
title bolded and ours reads flatter. Rendering producer HTML is not a trade
worth making — a Notification rule's message is operator-authored Jinja.
