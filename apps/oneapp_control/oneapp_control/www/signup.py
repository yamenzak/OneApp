import frappe
from frappe.utils import get_system_timezone

# The signup SPA owns routing under /signup, so a reload on the welcome page
# serves the same shell rather than 404ing.
no_cache = 1


def get_context(context):
	# Deliberately open to Guest, and the only page on this site that is.
	#
	# Signing up is the one thing somebody does before they have an account, so
	# redirecting to a login they cannot complete would make it impossible. That
	# is also why this outlived the rest of the control app's frontend: `/one`
	# sends a Guest to sign in, correctly, and this cannot.
	#
	# The page carries no customer data. Everything behind it is a whitelisted
	# method that resolves the workspace from the session and refuses anything
	# the caller does not own.
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
