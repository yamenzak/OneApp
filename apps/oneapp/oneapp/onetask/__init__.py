"""OneTask — the work, and the one table it lives in.

`docs/WORK.md` is the argument. The short version: a site installs the union of
what its granted spaces need, so a workspace that bought nothing using ERPNext
does not carry it — and this has to work for any business at all. So `One Task`
is ours, and it is the only task table in the product: a task in a project and
a task in somebody's own list are one row with and without a project on it.

What it is not is the assignment system. Frappe's ToDo stays exactly what it
is — a pointer at a record that already exists — and the two meet where a task
is assigned, through the framework's own path.
"""
