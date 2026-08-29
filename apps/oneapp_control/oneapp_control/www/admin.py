import frappe

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
		"socketio_port": frappe.conf.socketio_port or 9000,
		"csrf_token": frappe.sessions.get_csrf_token(),
	}
	context.no_cache = 1
	return context
