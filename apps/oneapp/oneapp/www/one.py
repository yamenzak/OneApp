import frappe

# The SPA handles its own routing under /one, so every path below it must serve
# the same shell rather than 404 on a deep link.
no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = (
			f"/login?redirect-to={frappe.request.path}"
		)
		raise frappe.Redirect

	context.no_cache = 1
	return context
