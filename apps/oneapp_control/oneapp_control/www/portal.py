import frappe

# The SPA owns routing under /portal, so every path below it serves the same
# shell rather than 404ing on a deep link.
no_cache = 1


def get_context(context):
	# Deliberately open to Guest. /portal/signup is the front door for someone
	# who does not have an account yet, and redirecting them to a login they
	# cannot complete would make signing up impossible. Everything that reads or
	# changes data is a whitelisted method that resolves the workspace from the
	# session and refuses anything the caller does not own — the page itself
	# carries no customer data.
	context.boot = {
		"site_name": frappe.local.site,
		"socketio_port": frappe.conf.socketio_port or 9000,
		"csrf_token": frappe.sessions.get_csrf_token(),
	}
	context.no_cache = 1
	return context
