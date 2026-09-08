"""What the platform itself adds to the agreements.

The suppliers that are not any one product's — where the workspace runs, who
takes the money, which models answer — and the clauses about the workspace as a
thing rather than about what is in it.
"""

from ..onelegal.registry import clause, subprocessor

M = "OneSpace"

subprocessor(
    name="Frappe Technologies Pvt. Ltd.",
    module=M,
    purpose="Frappe Cloud, the managed platform each workspace runs on: the "
            "site, its database, and its daily backups",
    data="Everything in the workspace",
    where="The region chosen when the workspace was created",
    safeguard="Standard Contractual Clauses and Frappe's data processing "
              "addendum",
    url="https://frappecloud.com/policies",
)

subprocessor(
    name="Hetzner Online GmbH",
    module=M,
    purpose="Server infrastructure underneath the managed platform in European "
            "regions",
    data="Everything in the workspace, at rest and in memory on the machine it "
         "runs on",
    where="Germany and Finland",
    safeguard="An EU processor; Standard Contractual Clauses where a transfer "
              "leaves the European Economic Area",
    url="https://www.hetzner.com/legal/privacy-policy",
)

subprocessor(
    name="Stripe, Inc.",
    module=M,
    purpose="Taking payment and holding the payment method",
    data="Billing contact, company name and address, and the card details you "
         "give Stripe directly — we never see them",
    where="The United States and Ireland",
    safeguard="Standard Contractual Clauses and Stripe's data processing "
              "agreement",
    url="https://stripe.com/legal/dpa",
)

subprocessor(
    name="Cloudflare, Inc.",
    module=M,
    purpose="Workers AI, which runs the open-weight models in our catalogue",
    data="The prompt a feature sends and the answer it gets back",
    where="Cloudflare's network, with inference on the nearest capable location",
    safeguard="Standard Contractual Clauses and Cloudflare's data processing "
              "addendum",
    url="https://www.cloudflare.com/cloudflare-customer-dpa/",
)

subprocessor(
    name="Google LLC",
    module=M,
    purpose="The Gemini models in our catalogue, through Google's API",
    data="The prompt a feature sends and the answer it gets back",
    where="The United States and Google's regional endpoints",
    safeguard="Standard Contractual Clauses and Google's Cloud data processing "
              "addendum; the API terms exclude training on submitted content",
    url="https://cloud.google.com/terms/data-processing-addendum",
)

clause(
    document="terms", section="modules", key="space-enable", module=M,
    body="""
        Turning a space on installs what that space needs and may add
        processing — a new doctype, a new integration, sometimes a new
        subprocessor. Where it does, you are shown what changes and asked to
        agree before it is enabled.
    """, order=5,
)

clause(
    document="privacy", section="modules", key="space-records", module=M,
    body="""
        A space's records hold whatever your organisation puts in them, which is
        usually about other people: customers, suppliers, employees. Who may see
        a record is decided by the workspace's own roles and by the framework's
        permission model, and every read goes through it.
    """, order=5,
)

clause(
    document="privacy", section="what", key="space-support", module=M,
    body="""
        If you ask us for support, we may need to sign in to your workspace to
        see the problem. Every such sign-in is recorded, is time-limited, and is
        visible to you.
    """, order=40,
)

clause(
    document="dpa", section="modules", key="space-isolation", module=M,
    body="""
        Each workspace is a separate site with its own database. There is no
        shared table of customer records and no query that can reach across
        workspaces.
    """, order=5,
)

clause(
    document="ai", section="modules", key="ai-features", module=M,
    body="""
        Every AI feature is declared in the product and listed in the
        workspace's AI settings, with the model it uses and what a run costs.
        An administrator can turn any of them off, and a feature that is off
        cannot be reached at all.
    """,
)
