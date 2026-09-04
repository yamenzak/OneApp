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

A `doctype()` call registers into `spec.DOCTYPES` by side effect, so importing
this package is what fills it — which is why every module is imported here
rather than only where it happens to be read.
"""

from . import ai, catalogue, fleet, importing, records, spaces  # noqa: F401
from .spec import (  # noqa: F401
    APPS, APPS_ROOT, DOCTYPES, GRANTED_GB, HANDLED_SPEC_KEYS, MANAGER_PERMS,
    READONLY_PERMS, STAMP, column, doctype, f, section,
)
