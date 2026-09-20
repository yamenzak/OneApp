# Integrations

## Frappe — the engine is a layer over it, not a replacement

**DocPerms are the permission model.** `sync_permissions` writes them from the
manifest and every read and write goes through them. The engine *reports* what
a person may do so the UI can hide what it must; it does not decide it.

**`Custom Field`** is how a space adds what a doctype lacks — applied by the
seeder rather than by migrate, which is why controllers guard on
`meta.has_field`.

**`Property Setter`** is how `sync_field_levels` raises a field above permlevel
zero: Frappe's own way of changing a field of somebody else's doctype without
forking it.

**`Notification`** is where an alert lands, typed `Alert` so it has a switch in
everybody's own Notifications panel.

**`Assignment Rule`** is what `routing.py` wears the face of.

**The socketio the bench already runs** carries presence, list updates and the
collaboration relay. No second runtime — `docs/COLLABORATION.md`.

## The control plane — `control_client.py`

The one door outward. Everything a tenant knows about its entitlements, its
plan, its credits and its spaces arrives through it, and is cached on
`OneSpace Site State` so a screen renders while the control plane is
unreachable.

`oneapp_control/entitlements/registry.py` is the other side, and
`registry.laddered` is the function that decides what a seat may touch.

## ERPNext and HRMS

**Nothing, deliberately.** The engine imports neither. What it renders of them
is what a space's manifest declares, which is why OneCRM and OneHR are
manifests plus behaviour rather than forks.

## Every space and every service

The engine is what they are written against:

* **`spaceview/actions.py`** — a space declares a verb and the engine offers it
  on the record and in the selection bar alike.
* **`mine.py`** — `@me`, resolved once and read by screens, by OneCalendar's
  `about` and by OneHR's assistant tools.
* **`showcase.py`, `recordviews.py`, `tabs.py`** — how a screen draws one
  record when a form is the wrong shape.
* **`dashboard.py`, `board.py`** — the widget and the board.
* **`words.py`** — the workspace's own word for a screen.
* **`seats.py`** — the four, on this side of the wire.

## OneAI

`spaceview.records.save` is what an Apply goes through, and `spaceview.resolve`
is what the assistant's tools resolve through — so the assistant sees exactly
what its asker could click to, and the engine did not have to know that.

`onespace_chat_tools` is the hook a module registers its own tools through.

## OneLegal

`legal.py` carries what the *platform* adds to the agreements, as opposed to
what a module does. `gate.outstanding` runs in front of everything on boot.

## OneCloud, OneMail, OneCalendar

Reached through the record shell: a record's Files tab, its Mail tab and its
calendar are the engine asking three services the same question about one
record.
