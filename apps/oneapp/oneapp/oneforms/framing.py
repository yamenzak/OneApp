"""Who may put a form inside their own page.

`docs/ONEFORMS.md` §14, stage 14. `allowed_embedding_domains` has been on
`Web Form` since Frappe shipped it and stage 14 finally gave it a control — and
the control was a lie for a day, which is why this file exists.

**Frappe enforces it in a renderer we never reach.**
`website/page_renderers/web_form.py` sets `frame-ancestors` while rendering
*its* web form route. Ours is `/one/f/<route>`, served by `www/one.py` through
`TemplatePage`, and that renderer has no headers path at all. So the setting
said "sites that may embed it" and every site could. Measured with `curl`: no
`X-Frame-Options`, no `Content-Security-Policy`, nothing.

`after_request` is where a `www` page can still answer, because it is handed the
response. It costs a string comparison on every request, which is the price of
the only place that works.

**Only ever narrowing, and only for a form.** Every other page under `/one` is
the workspace, and a workspace inside somebody else's page is how a click lands
on a control the reader cannot see. A form that names nobody gets
`frame-ancestors 'self'` — the honest reading of an empty list, because the
setting asks which sites may embed it and *none* is an answer.
"""

import re

import frappe

#: The one path that may be embedded.
EMBEDDABLE = "/one/f/"

#: The header. `X-Frame-Options` is the older one and cannot express a list, so
#: a form naming three sites would have to name none of them.
FRAMES = "Content-Security-Policy"

#: What a site may be written as. A scheme is allowed because people paste one;
#: a path, a space or a quote is either a mistake or an attempt to write the
#: rest of the header, and both are left out rather than argued with.
HOST = re.compile(r"^(?:https?://)?[A-Za-z0-9*.-]+(?::[0-9]{1,5})?$")


def framing(response=None, request=None) -> None:
	"""The `after_request` hook. See the module docstring for why it is one."""
	path = getattr(request, "path", "") or ""
	if not path.startswith(EMBEDDABLE) or response is None:
		return

	route = path[len(EMBEDDABLE):].strip("/").split("/")[0]
	if not route:
		return

	try:
		said = frappe.db.get_value(
			"Web Form", {"route": route, "published": 1},
			"allowed_embedding_domains") or ""
	except Exception:
		# A request that got this far without a usable connection is one whose
		# page already failed. Refusing to frame it is the safe answer and not
		# worth a traceback in the log.
		said = ""

	response.headers[FRAMES] = f"frame-ancestors {allowed(said)}"


def allowed(said: str) -> str:
	"""`'self'` plus whatever the form named, scrubbed.

	Scrubbed rather than passed through: this becomes a header, and a newline
	in a header is a second header.
	"""
	sites = [one.strip() for one in (said or "").replace(",", "\n").split("\n")]
	sites = [one for one in sites if one and HOST.match(one)]
	# `'self'` always, because the builder's own preview is this page.
	return " ".join(["'self'", *sites])
