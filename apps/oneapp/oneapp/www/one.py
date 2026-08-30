import frappe
from frappe.utils import get_system_timezone

# The SPA owns routing under /one, so every path below it serves the same shell
# rather than 404ing on a deep link.
no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
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
	}
	context.no_cache = 1
	return context
