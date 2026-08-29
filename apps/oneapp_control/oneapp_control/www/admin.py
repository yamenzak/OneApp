import frappe
from frappe.utils import get_system_timezone

# The SPA owns routing under /admin, so every path below it serves the same shell
# rather than 404ing on a deep link.
no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = f"/login?redirect-to={frappe.request.path}"
		raise frappe.Redirect

	if "System Manager" not in frappe.get_roles():
		raise frappe.PermissionError("The control plane is restricted to System Managers.")

	# frappe-ui's vite plugin injects these onto `window` for the SPA to read.
	# socketio_port matters in development, where Vite serves the app and the
	# socket has to be addressed on the bench directly rather than same-origin.
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
		"csrf_token": frappe.sessions.get_csrf_token(),
	}
	context.no_cache = 1
	return context
