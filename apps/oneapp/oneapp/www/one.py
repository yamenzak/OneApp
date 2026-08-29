import frappe

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
		"socketio_port": frappe.conf.socketio_port or 9000,
		"csrf_token": frappe.sessions.get_csrf_token(),
	}
	context.no_cache = 1
	return context
