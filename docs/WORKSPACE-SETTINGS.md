# Workspace settings: the audit

A tenant site is a real Frappe site with ERPNext on it, so most of what a
workspace needs to be *theirs* already exists — behind a desk the customer never
sees. This is the field-by-field record of what was moved into OneSpace, what
stayed ours, and what was left alone — a reference table rather than an
explanation, and one `tests/test_workspace_settings.py` reads back. The
reasoning is in `docs/ONESPACE.md`.

Three verdicts:

| | Meaning |
| --- | --- |
| **Customer** | In OneSpace → Settings. `oneapp_core/workspace.py` is both the renderer's spec and the write allowlist. |
| **Ours** | Set by the platform. Exposing it lets a workspace break itself in a way its owner cannot diagnose and we get the ticket. |
| **Neither** | Left at Frappe's default. Not harmful, not useful, and every field shown is a field someone has to understand. |

## Who sees which tab

The dialog was an admin's. Every tab in it was the workspace's, so it was
offered where `session.isAdmin` and nowhere else — and a member had no way to
change their own name, their own password, or what they were told about.

`oneapp_core/tabs.py` declares every tab with the audience it is for, and
`workspace.get()` returns the ones this reader may open. The shell draws exactly
those, so one dialog serves the owner and the member and neither is shown a door
that does not open. The gear in the rail is offered to everybody.

An audience is a **predicate, not a role**, because one of them is not a role:

| Audience | Who | Tabs |
| --- | --- | --- |
| `everyone` | Anybody signed in | Profile, Security, Notifications, Appearance |
| `mailbox` | Holds an address here — `mailbox._held()`, the same question every other mail endpoint asks | Mailbox |
| `admin` | `OneSpace Workspace Owner`, or our support as Administrator | Branding, Sign in, Regional, Books, Printing, Print formats, Naming, Email, Templates, Alerts, AI, Storage, Import |
| `support` | `System Manager` alone | The control plane's own groups, through `onespace_settings_groups` |

Nothing under Workspace is open to everybody, and every tab a member can open is
one of their own. Both are checked by `tests/test_settings_tabs.py`, along with
the two lists that have to agree with the declaration and fail silently when
they do not — the component that draws each panel, and the icon safelist, since
Tailwind's JIT does not read Python.

**Why mail is two tabs.** Email under Workspace is the workspace's: its domain,
who holds which address, which one notifications leave from, what it has sent
this hour. Mailbox under You is the same subject from the other end — the
signature on your own mail, your away message, your filing rules, and the
mailbox you have had for nine years and want to read here. They were one tab, so
a colleague who answers `sales@` could not set any of it: every endpoint under
it already asked who holds the address, but the only door to them was an admin's.

Email under Workspace is also where the two workspace-wide mail answers live:
the DNS for a domain the customer owns (`email/verify.py`, which had answered
those questions since it shipped and had nothing drawing them), and whether
members may connect an outside mailbox at all. Mailbox under You is where
somebody claims their own address, chooses which of theirs they write from, and
connects one of their own if the workspace allows it.

The signature appears on both, which is not a duplicate: it belongs to the
*address* rather than to the account — `signatures.py` holds Frappe's per-user
rule off for exactly that reason — so an admin sets it as the person who manages
the address, and its holder sets it as the person whose name is at the bottom of
the mail.

**Every image setting is published on the way in.** Everything the file picker
uploads is private, which is right for a workspace's files and wrong for the
four images whose job is to be seen by somebody who is not you: the logo and
favicon on the sign-in page and in the app's own tab, the splash, and a profile
picture. Left private
they 403 inside an `img` tag, which draws as nothing and explains nothing. So
`workspace.save` and `me.save_profile` both run the value through
`drive.writing.publish` first, which moves the file into the public half —
`public/files` on disk, the public prefix of the bucket on R2 — and stores the
URL that comes back. A picture is also attached to its own `User` row, the way
the desk does it, so deleting the file clears the field instead of leaving every
avatar pointing at a 404.

## What a person may change about themselves

`oneapp_core/me.py`, on the same two rules as `workspace.py`: the spec is the
allowlist, and every write names `frappe.session.user` rather than taking one.

| Field | Verdict | Why |
| --- | --- | --- |
| `User.first_name`, `last_name`, `user_image`, `mobile_no` | Theirs | Their name and how they are reached. The picture is the field every avatar in the product reads — the rail, the timeline, an assignment, a mail thread — so there is one image and not a second copy of it. |
| `User.language`, `User.time_zone` | Theirs | Per-person *overrides* of the workspace's regional settings, so a colleague in another country reads their own dates without changing anybody else's. Empty follows the workspace, and the panel says what that currently is. |
| `User.name` (the email) | **Neither** | The account's identity, and the seat is counted against it upstream — changing it is a control-plane act. Shown on the panel rather than hidden, because a profile with no address on it looks like it forgot. |
| `User.enabled`, `roles`, `role_profile_name`, `user_type`, `api_key`, `api_secret`, `username` | **Ours** | Administration. An endpoint that took a fieldname would be an endpoint that grants roles; `MINE` is a fixed set and `NEVER` names these again. |
| Password | Theirs | Through `check_password` then `User.save`, so the workspace's own policy — the minimum score an admin set under Sign in — is the rule that applies. |
| Sessions | Theirs, to end | `tabSessions` has no DocType over it, so it is read with SQL; its columns are user, sid, ipaddress and lastupdate, and none of them names a device. So the panel says when and from where, and offers "sign out everywhere else" rather than picking one row out of a list of near-identical ones. Everywhere *else* deliberately: the reason somebody reaches for it is a laptop they no longer have. |
| `Notification Settings` | Theirs | Frappe keeps one document per person. Already built (`oneapp_core/notifications.py`); it has a tab now instead of only a block on the Account page. |
| Theme | Theirs, in the browser | Not on the server at all. A round trip would only make the toggle slower. |
| Two-factor enrolment | **Not yet** | The workspace switch is an admin's and is built; enrolling *yourself* in an OTP app is a flow with a QR code and a verification step, which is a feature rather than a field. The panel says the workspace asks for one. |

## What this fixed on the way

**A tenant's sign-in page was Frappe-branded.** Nothing set `app_name` or
`app_logo`, so the one screen every user sees before they are anyone showed
Frappe's logo and the word "Frappe" — on a product whose premise is that
customers never see Frappe. `sync_branding` now names the workspace after itself
on the first sync, filling blanks only, so a customer's own choice is never
overwritten.

**ERPNext was installed and unusable.** Its setup wizard lives on the desk, so it
had never been run: no Company, no Fiscal Year, no chart of accounts, and
`setup_complete` at 0. Every accounting document would have failed for want of a
default company.

Books are now set up **at provisioning**, by the sync, from what signup already
answered — the region gives the country, the plan gives the currency, the
workspace name gives the company, and the country gives ERPNext's own default
chart and financial year. That is the same set of defaults its wizard offers and
most people accept, so a new workspace can invoice on day one rather than
discovering a missing default company at the worst moment.

What is assumed is announced. `status()` reports `assumed`, and OneSpace says so
and offers to start over — but only while nothing has been posted, because a
chart of accounts is structure the whole ledger hangs off. After the first entry
it is a migration, and the panel says that instead.

Setup is skipped rather than guessed when too little is known: no accounting app,
a company already there, a missing country or currency, or a country ERPNext
ships no verified chart for. Those workspaces are asked in OneSpace instead, which
is the flow that already existed.

The per-country financial years are ported from
`erpnext/public/js/setup_wizard.js`, the only place they exist and not somewhere
a Python caller can reach. A test re-reads that file where ERPNext is installed
and fails if the two have drifted — a workspace in the UK given a
January-to-December year has wrong books from its first invoice.

**`session.is_admin` answered the wrong question.** It keyed on System Manager,
which the workspace owner deliberately is not — so the person who administers the
workspace read as not an admin, and our support read as one.

## System Settings

| Field | Verdict | Why |
| --- | --- | --- |
| `app_name` | Customer | The workspace's name, written alongside Website Settings'. |
| `country`, `language`, `time_zone` | Customer | Regional. |
| `date_format`, `time_format`, `number_format`, `first_day_of_the_week` | Customer | Regional. |
| `currency`, `float_precision`, `currency_precision` | Customer | Regional. |
| `disable_user_pass_login` | Customer | Shown as "Password sign-in", inverted — a customer should answer "is this on". |
| `login_with_email_link`, `login_with_email_link_expiry` | Customer | Sends through the workspace's own Cloudflare address. |
| `enable_two_factor_auth`, `two_factor_method` | Customer | Method offers OTP App and Email only — see below. |
| `otp_issuer_name` | Ours | Follows the workspace name. Left at Frappe's default it names software the customer has never heard of, in the one place they look when locked out. |
| `session_expiry`, `deny_multiple_sessions` | Customer | Their security posture. |
| `enable_password_policy`, `minimum_password_score` | Customer | ditto. |
| `allow_consecutive_login_attempts`, `allow_login_after_fail` | Customer | ditto. |
| `force_user_to_reset_password` | Neither | Password rotation is discredited practice; offering it invites it. |
| `allow_login_using_mobile_number`, `allow_login_using_user_name` | Neither | A workspace's identity is email. A second namespace is a second thing to administer, and a third way to be locked out. |
| `enable_scheduler` | Ours | A workspace that can stop its own scheduler stops its own email, backups and syncs, and cannot see why. |
| `backup_limit`, `encrypt_backup` | Ours | Backups are Frappe Cloud's, per shard. |
| `max_file_size`, `allowed_file_extensions` | Ours | Storage is a billed quota; the cap belongs to the plan. |
| `allow_guests_to_upload_files`, `allowed_doctypes_for_guest_uploads` | Ours | Guest write access on a multi-tenant fleet. |
| `only_allow_system_managers_to_upload_public_files` | Ours | The owner is not a System Manager, so exposing this locks the owner out of uploads. |
| `enable_telemetry` | Ours | Off, fleet-wide. A customer's data is not ours to send anywhere. |
| `disable_standard_email_footer`, `email_footer_address` | Ours | The footer is white-label surface. |
| `default_app`, `setup_complete` | Ours | Where a session lands and whether ERPNext considers itself configured. |
| `log_api_requests`, `allow_error_traceback` | Ours | Tracebacks leak schema and code paths across a shared fleet. |
| `max_signups_allowed_per_hour` | Neither | Signup is off permanently — see Joining. |
| `apply_strict_user_permissions`, `disable_document_sharing`, `document_share_key_expiry` | Neither | Real settings, but sharing is not a feature this product exposes yet. Revisit with sharing. |
| `rounding_method`, `use_number_format_from_currency` | Neither | Accountant-grade; the wrong answer is silent and expensive. |
| `dormant_days`, `email_retry_limit`, `password_reset_limit`, `link_field_results_limit`, `max_report_rows`, `max_zip_extract_size`, `delete_background_exported_reports_after` | Ours | Fleet tuning. |

## Website Settings

| Field | Verdict | Why |
| --- | --- | --- |
| `app_name` | Customer | The name on the sign-in page. Read before System Settings'. |
| `app_logo` | Customer | The logo on the sign-in page. Written to Navbar Settings too, so support seeing the desk sees the same one. |
| `favicon` | Customer | Browser tab. |
| `splash_image` | Customer | Shown while the workspace loads — by the app, now that something reads it. |
| `disable_signup` | **Ours, forced on** | See Joining. |
| `footer_powered`, `copyright`, `banner_html` | Ours | White-label surface. |
| `head_html` | Ours, and we write to it | Never offered as a field — it is script injection on a shared fleet. But it is the only way a value reaches the pages Frappe renders for itself, so `oneapp_core/branding.py` writes the brand colour into it as a `<style>` block between markers, and leaves whatever else is in there alone. |
| `home_page`, `route_redirects`, `top_bar_items`, `footer_items`, `navbar_template`, `footer_template` | Neither | The public website is not a product surface; a tenant site serves the SPA. |
| `google_analytics_id`, `enable_google_indexing`, `enable_view_tracking` | Neither | No public site to measure. Indexing a tenant workspace would be actively wrong. |
| `hide_login`, `show_footer_on_login` | Neither | The sign-in page is ours to lay out; two half-controls of it are worse than none. |
| `show_account_deletion_link`, `auto_account_deletion` | Ours | Deleting an account here does not cancel a subscription or free a seat — deletion is a control-plane concern. |
| `robots_txt`, `subdomain` | Neither | ditto. |
| `website_theme` | **Ours** | The obvious home for a brand colour, and not one: `Website Theme.primary_color` is a Link to a bootstrap colour name, compiled into SCSS for the portal — a build step in the middle of a settings form, on a surface this product does not serve. The colour is a site default instead; see below. |

## The one setting with no Frappe field

**Brand colour.** One accent, under Branding, and the only thing in the dialog
that no doctype holds: it is `frappe.db.set_default("onespace_brand_accent")`,
for the reason in the Website Theme row above. It is an *intent* in the sense
`oneapp_core/theming.py` means it — the same validator, the same expansion into
CSS variables — and it lands in two places because a workspace is two
applications:

* the app gets it in the boot payload `www/one.py` builds, applied before first
  paint by `lib/shell/theme.js` as the floor a space's own theme stands on;
* the framework's own pages get it as a `<style>` block in `head_html`, because
  the sign-in page's Continue button is an espresso `.es-button` and espresso
  reads `--surface-gray-10` and `--ink-base` — the same two tokens the accent
  moves in the app.

So the sign-in page, an error page and the workspace behind them are one colour,
and a space that declares an accent of its own still wins inside itself. What is
**not** built: PWA assets. There is no web app manifest, no maskable icon set and
no service worker, so "add to home screen" gets the browser's own default. The
favicon is the workspace's now; a 192px and a 512px PNG are what a manifest would
additionally need, and neither the settings tab nor the storage layer generates
them yet.

## Navbar Settings

| Field | Verdict | Why |
| --- | --- | --- |
| `app_logo` | Customer | Written with Website Settings' so the two cannot disagree. |
| `settings_dropdown`, `help_dropdown` | Neither | Desk chrome. |
| `announcement_widget` | Neither | Desk chrome, and a place to inject HTML. |

## Sign-in methods

| Method | Status |
| --- | --- |
| Email + password | On by default, and can be turned off once another method works. |
| Email sign-in link | Offered. Frappe's `send_login_link` goes through `frappe.sendmail`, which on a tenant site is the workspace's own Cloudflare Email Service account — so it needs nothing extra. |
| Two-factor: OTP App | Offered. |
| Two-factor: Email | Offered, same sending path. |
| Two-factor: SMS | **Not offered.** Frappe supports it, but it needs an SMS gateway this platform does not run. It would fail at the moment someone is locked out, which is the worst moment to discover it. |
| Social login (Google, etc.) | **Not yet.** `Social Login Key` needs a client id and secret per provider, which means each workspace registering its own OAuth app — a real feature, not a settings row. Worth doing; not done here. |
| LDAP / SAML | No. Enterprise directory integration is a product decision, not a toggle. |

## Joining: invite only, permanently

Frappe has a signup form and turning it on is one line. It is off, and the toggle
is deliberately not offered. Three reasons, and any one of them is enough:

1. `frappe.core.doctype.user.user.sign_up` creates an **enabled Website User**
   with whatever role Portal Settings names, and no domain restriction. On a
   workspace at a guessable URL that is a stranger with an account.
2. Seats are counted and billed by the control plane against the workspace's
   member list. A user created here is invisible to that — open signup is a way
   to exceed a plan without paying for it.
3. Membership is reconciled *into* the site from the control plane, one way. An
   account the control plane does not know about is **disabled again on the next
   sync**. Open signup would not merely be unwise; it would produce accounts that
   stop working within the hour.

So people are invited from the workspace's People page, which adds them upstream
where the seat is counted and lets the sync create the account. `sync_branding`
re-asserts `disable_signup` every sync.

The shape that *would* work, if a customer asks for self-service joining, is
**domain-verified self-join**: someone with an address at a verified domain
requests to join, and the request creates a member upstream — where the seat is
counted — rather than a User here. That needs a tenant→control write endpoint
that does not exist yet.

## Print Settings

Printing is a workspace-wide decision and a per-document one, and these are the
first kind: a print format decides what is on the page, and this decides what
the page *is*. Every one of them is on Frappe's own `Print Settings` single,
and the desk's version of this page is the same eleven fields with three more
about a printer nobody in a browser has.

| Field | Verdict | Why |
| --- | --- | --- |
| `pdf_page_size`, `pdf_page_width`, `pdf_page_height` | Customer | The paper. Custom takes the two sizes in millimetres. |
| `font`, `font_size` | Customer | The typeface every format inherits unless it names its own. A Select, because it reaches a stylesheet the PDF engine must have the font for. |
| `print_style` | Customer | The typography and spacing a format is drawn in. |
| `pdf_generator` | Customer | Chrome renders modern CSS; wkhtmltopdf is an old WebKit and gets it wrong. Not interchangeable, which is why it is decided once for the workspace. |
| `with_letterhead` | Customer | Whether the letter head is on by default. |
| `repeat_header_footer` | Customer | Header and footer on every page rather than the first. |
| `allow_print_for_draft`, `allow_print_for_cancelled` | Customer | Whether an unsubmitted or cancelled document may leave the building. |
| `allow_page_break_inside_tables` | Customer | Off keeps a table whole and may leave a page short. |
| `enable_print_server`, `server_printer`, `enable_raw_printing` | **Withheld** | A network printer on the site's own LAN, and ESC/POS command strings. Neither means anything to a workspace reached over the internet, and `raw_commands` is a template that runs. |
| `send_print_as_pdf`, `view_link_in_email`, `add_draft_heading` | **Withheld** | Email composition, which belongs with email rather than with paper. |

## ERPNext

The wizard asks a lot; almost none of it is a setting.

| Area | Verdict | Why |
| --- | --- | --- |
| Company name, abbreviation | Customer, **at creation only** | The company is the docname. Renaming after entries exist is a rename operation across every ledger. |
| Country, currency, financial year | Customer, at creation only | Prefilled from what signup already established, so the company cannot disagree with the site about tax rules. |
| Chart of accounts template | Customer, at creation only | Read from ERPNext per country rather than listed here — it ships as JSON inside the app and changes with it. |
| `Company` (the other ~55 fields) | Neither | Default receivable account, round-off cost center, depreciation series. Accountant-grade, and mostly set by the chart. |
| `Accounts Settings` (60+ toggles) | Neither | Immutable ledger, deferred accounting, fuzzy party matching. Each one is a real decision for a real accountant and none is a workspace setting. |
| `Global Defaults` | Neither | Duplicates System Settings for country and currency; ERPNext reads those. |
| Demo data | Ours | Never installed. Demo transactions in a paying customer's ledger is not recoverable by them. |

## Every other singleton, and why the answer is one paragraph

A tenant site carries 70 singles: 31 from Frappe, 31 from ERPNext, 6 from HRMS
and 2 of ours. Four Frappe ones are above. The rest were read and the verdict is
a class rather than seventy rows, because writing seventy rows would imply
seventy decisions when there are four.

**ERPNext's twenty-odd `* Settings` singles are Neither.** `Selling Settings`,
`Buying Settings`, `Stock Settings`, `Manufacturing Settings`, `Projects
Settings`, `CRM Settings`, `Support Settings`, `POS Settings`, `Delivery
Settings`, `Item Variant Settings`, `Subscription Settings`, `Currency Exchange
Settings`, `Accounts Settings` — the same reasoning `Accounts Settings` already
carried, applied consistently. Each is a real decision for a real
practitioner and none is a *workspace* setting: "is a sales order required
before a delivery note" is a process policy for one company's operations, not a
preference like a date format. The wrong answer is silent and shows up in the
ledger a month later.

The escape hatch already exists and is better than a tab: a space declares a
**screen** over the doctype (`docs/APPS-AND-SPACES.md`), which gives the setting
a name in the customer's own words, a role that may reach it, and a place in the
navigation beside the work it governs. A fortieth tab in a shared dialog gives
it none of those.

**HRMS's `HR Settings` and `Payroll Settings` are Neither, for the same reason.**
Both are payroll and leave policy, both are per-company, and a workspace running
HR needs them in an HR space rather than under a gear shared with branding.

**Frappe's remaining singles split three ways.** *Ours*: `Log Settings`,
`Domain Settings`, `Session Default Settings`, `Push Notification Settings`,
`Global Search Settings`, `OAuth Provider Settings`, `Audit Trail` — fleet
plumbing, and several are ways to make a shard slow or leaky. *Neither*:
`About Us Settings`, `Contact Us Settings`, `Portal Settings`, `Website
Script`, `Desktop Settings`, `Geolocation Settings`, `Document Naming Settings`
— the public website and the desk are not product surfaces here, and naming is
already a tab of ours over the same machinery. *Not a setting at all*:
`Customize Form`, `Bulk Update`, `Data Export`, `System Console`, `Rename
Tool`, `Permission Inspector`, `Installed Applications`, `System Health
Report`, and ERPNext's tools (`BOM Update Tool`, `Bank Reconciliation Tool`,
`Chart of Accounts Importer`, `Leave Control Panel`, and the rest) — these are
desk *pages* that happen to be modelled as singles. A few have OneSpace
equivalents already (Import, Naming, People); the others are operator work.

**`Google Settings`, `SMS Settings`, `LDAP Settings`, `OAuth Settings` are
deferred rather than declined.** Each needs a credential per workspace and a
flow to obtain it, which is the same shape as social sign-in above: a real
feature, not a settings row. Recorded here so the next person does not
re-derive it.

**`Security Settings` exists on Frappe 17 and is empty of what we use.** Worth
saying because it looks like the answer: the auth fields this product exposes —
`enable_two_factor_auth`, `session_expiry`, `enable_password_policy` and the
rest — are still on `System Settings` on this bench, which is what the Sign in
group writes. If a Frappe release moves them, the group's targets move with
them and nothing else changes.
