"""How big a file may be, here, and who is allowed to say so.

There were two ceilings and neither was ever said out loud. WebDAV has one it
enforces and explains — `dav.py` returns a whole sentence with a 413 — and the
browser has one it does not mention at all: a person picks a 40 MB file, waits
for it to travel, and is told at the end that it was too big. The only size
messaging anywhere in the SPA was `FileSurface`'s "too big to *show* here",
which is about reading.

The number is not the same on every site, which is why it has to be asked for
rather than written down. Below `direct.THRESHOLD` a file is POSTed to Frappe
and the framework's own `max_file_size` bounds it. Above it the browser sends
the bytes straight to R2 in parts, and nothing between here and Cloudflare
reads the body — so on a site with a bucket there is no per-file ceiling worth
printing, and the thing that actually refuses is the quota, which says so in
its own words.

So: a number when there is one, and zero when there is not.

`docs/UNIFICATION.md` §D3.
"""

import frappe
from frappe.utils import cint

from oneapp.onestorage import r2
from oneapp.onespace import site

#: Frappe's own default, from `init_request`. Named here because the config key
#: is usually absent and 25 MB is then the real answer rather than "unset".
FRAMEWORK_DEFAULT = 25 * 1024 * 1024


def posted_ceiling() -> int:
	"""The largest body Frappe itself will accept on this site.

	Frappe's own expression, from `init_request`, and deliberately not
	`frappe.core.api.file.get_max_file_size` — that one consults System
	Settings first, but only for `/api/method/upload_file`, so quoting it on
	any other path names a number that does not apply.
	"""
	return cint(frappe.local.conf.get("max_file_size")) or FRAMEWORK_DEFAULT


def browser_ceiling() -> int:
	"""The largest single file a browser may put in, or 0 for no fixed one.

	Zero wherever the direct path is available, because then the bytes never
	pass through the framework and the only thing that refuses a large file is
	the quota — which has its own message and its own number.
	"""
	if site.is_control() or not r2.is_configured():
		return posted_ceiling()
	return 0


def boot() -> dict:
	"""What the SPA needs before it draws an attach control.

	Before first paint rather than on a resource, because the sentence belongs
	*under the control* — a limit a person reads after choosing the file is a
	limit they have already spent a minute on.
	"""
	return {"file": browser_ceiling()}
