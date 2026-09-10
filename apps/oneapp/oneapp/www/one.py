import frappe
from frappe.utils import get_system_timezone

from oneapp.onespace import basemap, branding
from oneapp.onespace.ai import settings as ai_settings

# The SPA owns routing under /one, so every path below it serves the same shell
# rather than 404ing on a deep link.
no_cache = 1


# The one path below /one a stranger is allowed to reach. Every other screen
# here is a window onto a workspace they have no account in, so the framework's
# own answer — go and sign in — is the right one. A shared link is not: the
# secret in the URL *is* the credential, and sending its holder to a sign-in
# page they cannot pass sends them nowhere. See `onestorage/linked.py`.
LINK_PREFIX = "/one/link/"


def get_context(context):
	guest = frappe.session.user == "Guest"
	if guest and not (frappe.request and frappe.request.path.startswith(LINK_PREFIX)):
		frappe.local.flags.redirect_location = f"/login?redirect-to={frappe.request.path}"
		raise frappe.Redirect

	# Injected onto `window` by frappe-ui's vite plugin. socketio_port matters in
	# development, where Vite serves the app and the socket cannot be same-origin.
	context.boot = {
		"site_name": frappe.local.site,
		# Frappe stores datetimes in the *system* timezone. Without this the SPA
		# renders them as if they were the reader's own — an invoice dated the
		# 1st reads as the 31st for anyone far enough west. `dayjsLocal` does the
		# conversion, and this is the half it cannot know by itself.
		"system_timezone": get_system_timezone(),
		# Who is signed in. The SPA needs the id to fetch the User doc: there
		# is no user named "me", so frappe.client.get on it 404s and the HTML
		# error page comes back to be parsed as JSON.
		"user": frappe.session.user,
		"socketio_port": frappe.conf.socketio_port or 9000,
		# Whether anything in front of this origin routes `/socket.io/` to that
		# port. In production nginx does; on a bench nothing does, and the
		# socket has to be addressed on the port itself — which is the same
		# call Frappe's own desk client makes from `window.dev_server`.
		"dev_server": 1 if frappe.conf.developer_mode else 0,
		"csrf_token": frappe.sessions.get_csrf_token(),
		# What this workspace looks like, before anything is fetched: the accent
		# a solid button is, the tab icon, and the image shown while the session
		# loads. Here rather than on the session resource because all three are
		# wanted before first paint — a favicon that arrives after a round trip
		# is a tab that visibly changes. See `onespace/branding.py`.
		"brand": branding.boot(),
		# Which language to draw in. `frappe.local.lang` is already the answer
		# the framework worked out for this request — the reader's own if they
		# set one, the workspace's otherwise — so this is that answer handed
		# forward rather than a second guess at it. Before first paint because
		# Arabic is not a repaint, it is the layout running the other way. A
		# guest gets it too: the workspace's own language is the one its link
		# bar should be reading in.
		"lang": frappe.local.lang or "en",
	}

	if not guest:
		# Everything below describes the workspace, and somebody holding a link
		# is not in one. `Linked.vue` draws a single file: it asks for no
		# assistant and no map.
		# Who the assistant is. Here rather than on the AI settings resource
		# because the chat rail, the panel header and the breadcrumb all name it
		# before anything is fetched — and a header that says "Assistant" for a
		# moment and then says "Rua" is the same visible flicker the favicon
		# had. See `onespace/ai/settings.py`.
		context.boot["assistant"] = ai_settings.identity()
		# Where a map gets its ground: `{ style, tiles, dark, attribution }`.
		# A deployment fact rather than a workspace's, so it rides the boot
		# payload rather than a screen's — every map surface reads the same
		# answer and an air-gapped install changes it in one place. See
		# `onespace/basemap.py`.
		context.boot["basemap"] = basemap.boot()

	context.no_cache = 1
	return context
