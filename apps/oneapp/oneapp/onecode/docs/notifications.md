# Notifications

**OneCode sends nothing.** It ships no rule in any space manifest's `ALERTS`
and registers no `doc_events` hook of its own.

That is the right answer rather than a gap. The events worth hearing about
around a code file — somebody shared it with you, somebody commented, a version
was written — belong to the `File` those things happened to, and OneCloud sends
them. A second notification from this module about the same event would be two
notifications about one thing.

When serving lands (the README's item 1), the event that will be worth a rule
is a project's route being claimed or released, because that changes what a URL
on the workspace's own host does. Nothing else about editing a file is.
