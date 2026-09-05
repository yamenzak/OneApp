# Apps and Spaces

Which Frappe apps a tenant's site carries, which Spaces it is entitled to, and
what happens when a Space needs something of the schema. Three layers that are
easy to conflate, one of which is currently doing a job it should not.

Read `docs/ONEADMIN.md` first for tenancy and the control plane. This is the
part that decides what is *on* a site.

---

## 1. What is true today

### One site per tenant

Provisioning asks press for a site per tenant (`provisioning/steps.py`,
`create_site`), so a tenant is a Frappe **site**: its own database, its own
`tabSingles`, its own Custom Fields. This is the answer to the question that
prompted this document, and it is the reassuring one:

> RUA's space adds `custom_retention_percentage` to Sales Invoice. Does every
> tenant get it?

**No.** That field is a `Custom Field` row in RUA's own database. Nobody else's
site has a row in `tabCustom Field` naming it, and nobody else's Sales Invoice
grows a column. Tenancy here is site-level, not row-level, and site-level
tenancy is what makes per-customer schema safe at all.

The customisation is not shipped in the app either — `oneapp/hooks.py` declares
no `fixtures`, so nothing in `plans/rua.py` reaches a site that did not ask for
it.

### Apps are per **shard**, not per tenant and not per space

`site_apps(shard)` reads `Shard.site_apps`, defaulting to
`frappe,erpnext,hrms,oneapp`. Every site created on that shard gets that list.
A `Shard` is a press release group — a bench — so this is really "what the
bench carries", and it is the only thing that decides.

Consequences, all of them true right now:

* A tenant who bought nothing but OneSpace's own registers still carries
  ERPNext and HRMS: about fifteen hundred doctypes, their tables, their
  patches on every migrate, and their weight in every backup.
* Moving a tenant to a shard whose bench lacks an app silently changes what
  their spaces can draw.
* There is no way to say "this tenant needs ERPNext" other than putting them
  on a bench that has it.

### A Space does not declare what it needs

`OneSpace Space` carries `screens`, `roles`, `doctypes`, `theme`,
`availability`. It does **not** carry which Frappe apps its screens assume, and
it does not carry the schema its screens read.

Both absences fail the same way — **silently**:

* `sync_permissions` skips a doctype the site does not have, with a comment
  saying that is deliberate ("the manifest describes the catalogue, not this
  tenant"). Right, and it means granting RUA to a site without ERPNext produces
  a space whose every screen is empty and no error anywhere.
* `_columns` skips a field the site does not have, for the same reason. So a
  screen that lists `custom_retention_percentage` on a site where nothing
  created it simply has one column fewer.

### The schema is hooked to the wrong thing

RUA's ten Custom Fields live in `plans/rua.py` as `FIELDS`, and they are
created by `plans.prepare()`, which runs from `plans.install()` — the **import
plan**. So the fields exist because somebody set up a data migration, not
because the tenant was granted the space.

A tenant granted RUA who never imports anything gets RUA's screens without
RUA's fields. That is the one real bug in this area, and it is invisible: the
screens render, they are simply missing columns.

---

## 2. What is wrong with it

Ordered by how much it costs, not by how easy it is to fix.

1. **Every tenant pays for every app.** Migration time, backup size, database
   size, and the upgrade risk of code nobody on that site runs.
2. **A space's requirements are undeclared, so they cannot be checked.** The
   grant succeeds and the screens are empty.
3. **A space's schema is undeclared, so it arrives with the importer or not at
   all.**
4. **`Shard.site_apps` is a bench fact being used as a tenant fact.** The two
   are different questions and only one of them belongs to the customer.

---

## 3. The shape of the answer

**The Space is the unit of everything.** It already declares its screens, its
roles and the doctypes it may reach. It should also declare the two things it
assumes about the site it lands on:

```
requires_apps   erpnext            what its screens are written against
custom_fields   [{dt, fieldname…}] what its screens read that the doctype lacks
```

And a tenant's site is then **the union of what its granted spaces need**, plus
a base every site has (`frappe`, `oneapp`).

That gives three things at once, in the shape this codebase already uses
everywhere — declare it, check it, apply it once:

### A. `requires_apps` — checked before the grant

* Granting a space to a tenant whose site lacks an app is refused, with the app
  named, rather than succeeding into empty screens.
* OneAdmin can say *why* a space is not offerable to a tenant.
* Provisioning computes a new site's app list from the spaces the tenant is
  being given, rather than from the bench's default.

The bench still has to *have* the app — `Shard.site_apps` becomes the ceiling
rather than the answer, which is the correct relationship: a bench carries a
superset, a site installs a subset.

### B. `custom_fields` — applied by the sync, once

Through `sync_screen_fixtures`, which is exactly the right existing path and
already documents why: a series prefix and a print format are applied the first
time they are seen and never again, because a workspace edits them afterwards
and reapplying would undo an afternoon's work every fifteen minutes. A Custom
Field is the same kind of thing.

Then:

* Granting RUA gives you RUA's fields. The importer stops being where schema
  comes from and goes back to being a data migration.
* A space's screens and the fields they read are declared in one file.
* Revoking a space leaves the fields alone, which is right: they may hold data.

### C. Per-tenant app lists

`Tenant.site_apps`, computed from the union above and stored so a rebuild is
reproducible. New sites get exactly what they need.

Adding an app to a **live** site is a migration and a real operation — press
supports it, it takes minutes, and it can fail. That is a provisioning job of
its own with its own state, and it is the one part of this that should not be
built casually. Until it exists, granting a space that needs an app the site
lacks is refused with a sentence saying so, which is already better than the
silence.

---

## 4. What was built

**A and B.** A space declares `requires_apps` and `custom_fields`; the
entitlement refuses a grant the site cannot support and says which app is
missing; the sync applies a space's fields once, as a fixture; RUA's ten fields
moved from its import plan to its space, and the plan now assumes rather than
creates them.

**C is designed and not built.** Installing an app onto a live site is a
migration, and the failure mode of getting it wrong unattended is a tenant
whose site is half-migrated. The refusal in A is the honest interim: it names
the app, and an operator moves the tenant or installs it deliberately.
