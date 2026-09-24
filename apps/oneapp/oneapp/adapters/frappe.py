"""The framework, and what this product does to it.

Frappe is not a dependency the way ERPNext is. This *is* a Frappe app: every
module imports `frappe`, every endpoint is a `@frappe.whitelist()`, every
doctype is theirs by construction. Listing that would be listing the language.

So the line this adapter draws is **the documented surface against the
internals**. `frappe.utils`, `frappe._`, `frappe.model.document.Document` and
the decorators are what every app in the ecosystem uses and are not a seam.
What is below is: a doctype controller of theirs that we subclass, a method of
theirs we replace, a class the mail receiver builds that we reach inside. Those
are the ones an upgrade breaks, and they are the ones here.

Three of the seven controllers are the same idea — the framework knows
something at the moment of doing and throws it away before anything can read
it. A folder on an inbound message, a quota at the moment of upload, a signature
the composer has already placed.
"""

APP = "frappe"
NAME = "Frappe"

#: Their doctype, our controller.
SUBCLASSED = {
	"File": "`onestorage/file.py`. The one doctype in this product that is "
	        "genuinely extended rather than wrapped: OneCloud, OneWriter and "
	        "OneWorkbook are all views onto core `File`, which is what "
	        "`docs/DRIVE.md` argues for and what keeps a document, a sheet "
	        "and an attachment one table.",
}

#: Their doctype, our handler beside theirs.
HOOKED = {
	"File": "Six handlers, and they are four different questions. The quota "
	        "at upload time, because discovering you are 3 GB over after the "
	        "fact is worse than a clear rejection now; what the file *is*, so "
	        "the drive filters on a column rather than walking a mime map per "
	        "row; and three sweeps on trash — a sheet's grid, a document's "
	        "prose and the records a file was read against are all rows keyed "
	        "by the File, and the File being deleted is the only thing that "
	        "knows they exist.",
	"Version": "`onespace/notifications.py`. Frappe stores a follow and then "
	           "only ever emails a digest about it; this is the in-app half. "
	           "Version rather than `on_update` for `*`, because a Version "
	           "row exists only where `track_changes` is on, which is exactly "
	           "the condition a document has to meet to be followable.",
	"Comment": "The other half of the same: a comment on something you "
	           "follow, and an @mention.",
	"*": "Six handlers on every doctype in the site, and each earns it. Two "
	     "are OneAI's index. Two are OneAI's written-value cache, which has "
	     "to forget on any save. One is OneCRM's answering clock, which stops "
	     "when anything is written against a lead or a deal. One is the "
	     "database quota, which is the only place a row count can be "
	     "refused.",
}

#: Their tables carrying a column of ours. None: every custom field this
#: product declares is on an ERPNext or HRMS doctype. What we add to Frappe's
#: own tables we add by subclassing or by a doctype of our own keyed to theirs
#: — a `File Version` beside a File, a `Bound Record` beside a Communication —
#: which is the shape that survives a framework upgrade.
EXTENDED = {}

#: Their internals we reach into. Not `frappe.utils`, `frappe._` or
#: `Document`: those are the documented surface every app uses, and listing
#: them would be listing the language.
CALLED = {
	"frappe.core.doctype.file.file.File":
		"The base class `OneSpaceFile` subclasses.",
	"frappe.rate_limiter.rate_limit":
		"On the endpoints a signed-out caller can reach.",
}
