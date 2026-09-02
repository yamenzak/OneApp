# Workspace settings: the audit

A tenant site is a real Frappe site with ERPNext on it, so most of what a
workspace needs to be *theirs* already exists — behind a desk the customer never
sees (DECISIONS §7). This is the field-by-field record of what was moved into
OneSpace, what stayed ours, and what was left alone.

Three verdicts:

| | Meaning |
| --- | --- |
| **Customer** | In OneSpace → Workspace settings. `oneapp_core/workspace.py` is both the renderer's spec and the write allowlist. |
| **Ours** | Set by the platform. Exposing it lets a workspace break itself in a way its owner cannot diagnose and we get the ticket. |
| **Neither** | Left at Frappe's default. Not harmful, not useful, and every field shown is a field someone has to understand. |

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
| `splash_image` | Customer | Shown while the workspace loads. |
| `disable_signup` | **Ours, forced on** | See Joining. |
| `footer_powered`, `copyright`, `banner_html`, `head_html` | Ours | White-label surface, and `head_html` is script injection on a shared fleet. |
| `home_page`, `route_redirects`, `top_bar_items`, `footer_items`, `navbar_template`, `footer_template` | Neither | The public website is not a product surface; a tenant site serves the SPA. |
| `google_analytics_id`, `enable_google_indexing`, `enable_view_tracking` | Neither | No public site to measure. Indexing a tenant workspace would be actively wrong. |
| `hide_login`, `show_footer_on_login` | Neither | The sign-in page is ours to lay out; two half-controls of it are worse than none. |
| `show_account_deletion_link`, `auto_account_deletion` | Ours | Deleting an account here does not cancel a subscription or free a seat — deletion is a control-plane concern. |
| `robots_txt`, `subdomain`, `website_theme` | Neither | ditto. |

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
