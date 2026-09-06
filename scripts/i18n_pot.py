"""Regenerate `main.pot` for both of our apps.

    scripts/dev.sh run scripts/i18n_pot.py

Not part of `scripts/i18n.py` because extraction needs a site: the framework
walks the app for `_()` and `__()` calls through Babel, and reaches for hooks
and installed-app lists on the way. Everything downstream of the POT — what is
already translated upstream, what is still ours — needs nothing but the files,
and lives there.

If this prints nothing and writes nothing, the app's `babel_extractors.csv` has
gone missing; `tests/test_i18n.py` says why that file exists.
"""

from frappe.gettext.translate import generate_pot

for app in ("oneapp", "oneapp_control"):
	generate_pot(app)
