"""Every doctype in both apps, declared.

`scripts/gen_doctypes.py` turns what is here into the JSON files Frappe reads;
this package is the declarations themselves, grouped by subject:

  spec       the vocabulary — `f`, `section`, `column`, `doctype`
  fleet      tenants, shards, regions, provisioning, lifecycle
  catalogue  plans, add-ons, packs, promos, subscriptions, the ledger
  ai         models, prices, features, usage
  spaces     spaces, screens, roles, saved views, control settings
  records    tenant-side records: compliance, correspondence, mail rules
  importing  sources, plans, runs, issues, identities
  mobility   the reference nouns of a transit network — and not its facts,
             which are `oneapp/onemobility/model.py` against `shared/facts.py`

A `doctype()` call registers into `spec.DOCTYPES` by side effect, so importing
this package is what fills it — which is why every module is imported here
rather than only where it happens to be read.
"""

from . import (  # noqa: F401
    ai, catalogue, fleet, importing, mobility, records, spaces,
)
from .spec import (  # noqa: F401
    APPS, APPS_ROOT, DOCTYPES, GRANTED_GB, HANDLED_SPEC_KEYS, MANAGER_PERMS,
    MODULE_DIRS, READONLY_PERMS, STAMP, column, doctype, f, section,
)
