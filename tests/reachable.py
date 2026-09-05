"""Every dotted path a whitelisted method answers to.

A method in a package is callable at its own module's path *and* at the
package's, when the package re-exports it. `spaceview` is a package of layered
modules whose `__init__` re-exports everything, precisely so that
`oneapp.oneapp_core.spaceview.rows` keeps working — and that is the path the SPA
calls. A guard that reads only the filename declares every one of those missing.
"""

import re
from pathlib import Path


def paths(path: Path, dotted: str, name: str) -> list[str]:
	"""`module.name`, plus `package.name` where the package re-exports it."""
	found = [f"{dotted}.{name}"]
	init = path.parent / "__init__.py"
	if path.name != "__init__.py" and init.exists():
		if re.search(rf"\b{re.escape(name)}\b", init.read_text()):
			found.append(f"{dotted.rsplit('.', 1)[0]}.{name}")
	return found
