#!/usr/bin/env python3
"""Hand a fresh control site the credentials it needs to do anything.

A new control plane has nobody signed in and nothing configured, so it cannot be
told its own Frappe Cloud keys through its own UI. Press can write a site's
config over its API, which makes that the one channel reaching it first.

    scripts/bootstrap_site.py oneadmin.frappe.cloud

Reads PRESS_KEY and PRESS_SECRET from ONEAPP_FC_ENV. The settings doctype still
wins over site config once someone sets it there, so this is a starting point
rather than a permanent home — see PressClient.

It also writes `oneapp_role = "control"`, which is the other thing a control
site cannot be told through its own UI and the one with the worst failure mode:
absent means tenant, and a control plane running as a tenant looks fine while
its File override sends attachments to a bucket it does not have and two
scheduled jobs call a control plane that is itself. Pass a second argument to
set a different role; pass `tenant` for a site that is one, where the key is
removed rather than written.
"""

import json
import os
import sys
import urllib.error
import urllib.request

PRESS_URL = os.environ.get("PRESS_URL", "https://cloud.frappe.io")


def press(method: str, payload: dict, timeout: int = 180) -> dict:
    key, secret = os.environ.get("PRESS_KEY"), os.environ.get("PRESS_SECRET")
    if not (key and secret):
        sys.exit("PRESS_KEY and PRESS_SECRET are not set — see ONEAPP_FC_ENV.")
    request = urllib.request.Request(
        f"{PRESS_URL}/api/method/{method}",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"token {key}:{secret}",
            "Content-Type": "application/json",
        },
    )
    try:
        return json.loads(urllib.request.urlopen(request, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} failed: HTTP {e.code} {e.read().decode()[:400]}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    site = sys.argv[1]
    role = sys.argv[2] if len(sys.argv) > 2 else "control"

    env_file = os.environ.get("ONEAPP_FC_ENV")
    if env_file and os.path.exists(env_file):
        for line in open(env_file):
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    # The API takes a list of {key, value, type}; the doc method takes a
    # mapping. Passing the wrong one makes press iterate keys as strings and
    # fail with a bare ValueError.
    config = [
        {"key": "press_api_url", "value": PRESS_URL, "type": "String"},
        {"key": "press_api_key", "value": os.environ["PRESS_KEY"], "type": "String"},
        {"key": "press_api_secret", "value": os.environ["PRESS_SECRET"], "type": "String"},
    ]
    # Declared, never derived: `docs/ONEADMIN.md` §10 is why asking "is
    # oneapp_control installed?" would be the wrong question.
    if role != "tenant":
        config.append({"key": "oneapp_role", "value": role, "type": "String"})
    press("press.api.site.update_config", {"name": site, "config": json.dumps(config)})

    # Read it back. Press drops empty values silently, so a write that reports
    # success is not proof the key landed — that once left a site permanently
    # unable to reach its control plane, with every step reporting fine.
    written = press("press.api.site.site_config", {"name": site}).get("message") or []
    present = {row.get("key") for row in written}
    missing = [c["key"] for c in config if c["key"] not in present]
    if missing:
        sys.exit(f"These keys did not land: {missing}")

    print(f"{site}: press credentials in place ({', '.join(sorted(present))})")
    if role != "tenant":
        print(f"{site}: oneapp_role = {role}")
    print("Sign in as Administrator and finish setup in Settings — the rest "
          "(control plane URL, tenant domain, Stripe, Cloudflare) is entered there.")


if __name__ == "__main__":
    main()
