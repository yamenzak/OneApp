#!/usr/bin/env python3
"""Push the working tree onto a running Frappe Cloud bench, as a patch.

Development only. A patch is `git apply` inside the running container — seconds,
no image build — but it exists in no image, so **the next deploy silently
reverts it**. Nothing here is a way to ship.

    scripts/live.py status     what the bench is running, and what we have patched
    scripts/live.py push       send everything since the deployed commit
    scripts/live.py revert     remove our patch, back to the deployed image
    scripts/live.py watch      push on every change (Ctrl-C to stop)

Credentials come from ONEAPP_FC_ENV (default: the file named below), which sets
PRESS_KEY and PRESS_SECRET.

Assets: `--assets` includes the built SPA. It is off by default because the
bench cannot build it — `build_assets` runs `bench build`, which is Frappe's own
esbuild and knows nothing about Vite — so the bundle has to travel in the patch,
and that only applies cleanly when our build reproduces the deployed one byte
for byte. See docs/DEVLOOP.md.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESS_URL = os.environ.get("PRESS_URL", "https://cloud.frappe.io")
STATE = ROOT / ".oneapp-live.json"

# Built output, which git ignores on purpose but a patch may need to carry.
ASSET_PATHS = ["{app}/{app}/public/frontend", "{app}/{app}/www"]


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
        body = e.read().decode()[:400]
        # press returns exc_type and nothing about which parameter was wrong, so
        # echo the whole body rather than a tidied summary.
        sys.exit(f"{method} failed: HTTP {e.code} {body}")


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def deployed_commit(group: str, app: str) -> tuple[str, str]:
    """The monorepo commit the bench is running, and the mirror hash.

    Read from press rather than inferred. The obvious shortcut — matching the
    built asset hash — identifies a *range*, not a commit: any two commits that
    did not touch frontend source produce an identical bundle.
    """
    info = press("press.api.bench.deploy_information", {"name": group})["message"]
    entry = next((a for a in info["apps"] if a["app"] == app), None)
    if not entry:
        sys.exit(f"{app} is not on {group}.")

    mirror_hash = entry["current_hash"]
    release = press(
        "press.api.client.get_list",
        {
            "doctype": "App Release",
            "filters": {"hash": mirror_hash},
            "fields": ["name", "message"],
            "limit_page_length": 1,
        },
    )["message"]
    if not release:
        sys.exit(f"No App Release for {mirror_hash[:10]}; cannot find the base.")

    # The mirror's commit subject is the monorepo's, copied by the sync workflow.
    subject = (release[0]["message"] or "").split("\n")[0]
    found = git("log", "--format=%H", "-1", "--fixed-strings", f"--grep={subject}").strip()
    if not found:
        sys.exit(f"No local commit matching {subject!r} — is this branch behind?")
    return found, mirror_hash


def build_patch(app: str, base: str, with_assets: bool) -> str:
    """Everything from the deployed commit to the working tree, mirror-relative."""
    parts = [git("diff", base, "--", f"apps/{app}")]

    if with_assets:
        paths = [p.format(app=app) for p in ASSET_PATHS]
        prefixed = [f"apps/{p}" for p in paths]
        git("add", "-Af", *prefixed, check=False)
        git("reset", "-q", "--", f":(glob)apps/{app}/**/__pycache__/**", check=False)
        # --binary or the woff2 fonts arrive as placeholders and git apply
        # rejects the whole patch.
        parts.append(git("diff", "--cached", "--binary", "--", *prefixed))
        git("reset", "-q", "--", *prefixed, check=False)

    # The agent applies from apps/<app> in the container, which knows nothing
    # about this monorepo, so the prefixes have to go.
    return "".join(parts).replace(f"a/apps/{app}/", "a/").replace(f"b/apps/{app}/", "b/")


def revert_patch(name: str):
    """Undo an applied patch through press, not by flipping the diff ourselves.

    App Patch.revert_patch re-runs `git apply --reverse` against the exact patch
    file the agent stored. Reversing a diff by hand looks equivalent and is not:
    new-file and deleted-file hunks have to be rewritten, and getting one wrong
    leaves the bench in a state where nothing further applies — which is exactly
    what happened before this used the real API.
    """
    press(
        "press.api.client.run_doc_method",
        {"dt": "App Patch", "dn": name, "method": "revert_patch", "args": json.dumps({})},
    )
    for _ in range(30):
        time.sleep(8)
        doc = press("press.api.client.get", {"doctype": "App Patch", "name": name})
        status = (doc.get("message") or {}).get("status")
        if status == "Not Applied":
            return
        if status == "Failed":
            sys.exit(f"Reverting patch {name} failed; the bench needs a deploy to reset.")
    sys.exit(f"Revert of {name} still pending after several minutes.")


def apply(group: str, app: str, patch: str, label: str, build_assets: bool) -> str:
    result = press(
        "press.api.bench.apply_patch",
        {
            "release_group": group,
            "app": app,
            # A nested object, not a JSON string: press does not parse this one,
            # and a string makes it raise AttributeError server-side.
            "patch_config": {
                "patch": patch,
                "filename": f"{label}.patch",
                "build_assets": build_assets,
                "patch_all_benches": False,
                "patch_latest_deploy": True,
            },
        },
    )
    ids = result.get("message") or []
    if not ids:
        sys.exit(f"apply_patch returned nothing: {result}")

    name = str(ids[0])
    for _ in range(40):
        time.sleep(10)
        doc = press("press.api.client.get", {"doctype": "App Patch", "name": name})
        status = (doc.get("message") or {}).get("status")
        if status in ("Applied", "Failed"):
            if status == "Failed":
                # Agent Job output is not exposed to the API, so there is
                # nothing more specific to report than this.
                sys.exit(
                    f"Patch {name} failed. Almost always a base mismatch — run "
                    f"`live.py status` and check the bench is on the commit you "
                    f"diffed from."
                )
            return name
    sys.exit(f"Patch {name} still pending after several minutes.")


def read_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def write_state(data: dict):
    STATE.write_text(json.dumps(data, indent=1))


def tree_fingerprint(app: str) -> str:
    """Changes since HEAD plus HEAD itself — enough to notice any edit."""
    return hashlib.sha256(
        (git("rev-parse", "HEAD") + git("diff", "HEAD", "--", f"apps/{app}")).encode()
    ).hexdigest()


def cmd_status(args):
    base, mirror = deployed_commit(args.group, args.app)
    subject = git("log", "--format=%s", "-1", base).strip()
    state = read_state()
    print(f"bench   {args.group} / {args.app}")
    print(f"running {mirror[:10]}  = {base[:10]}  {subject}")
    print(f"local   {git('rev-parse', '--short', 'HEAD').strip()}  {git('log', '--format=%s', '-1').strip()}")
    if state.get("patch"):
        print(f"patched {state['label']} (App Patch {state['app_patch']}) at {state['at']}")
    else:
        print("patched nothing")


def cmd_revert(args, quiet: bool = False):
    state = read_state()
    if not state.get("app_patch"):
        if not quiet:
            print("Nothing patched.")
        return
    revert_patch(state["app_patch"])
    write_state({})
    if not quiet:
        print("Reverted to the deployed image.")


def cmd_push(args):
    base, _ = deployed_commit(args.group, args.app)
    patch = build_patch(args.app, base, args.assets)
    if not patch.strip():
        print("Nothing to push — the working tree matches the bench.")
        return

    # Undo our previous patch first. The container is cumulative, so re-applying
    # an overlapping diff would conflict on context that is already changed.
    cmd_revert(args, quiet=True)

    # Unique per bench forever, not just per session: press rejects a filename
    # it has seen before on that bench — even one whose patch was reverted —
    # with "Patch already exists for <bench> by the filename ...". The content
    # hash also makes an unchanged re-push obvious in the patch list.
    digest = hashlib.sha256(patch.encode()).hexdigest()[:8]
    label = time.strftime("live-%Y%m%d-%H%M%S-") + digest
    name = apply(args.group, args.app, patch, label, args.assets)
    write_state({
        "label": label,
        "app_patch": name,
        "base": base,
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    print(f"Applied {label} ({len(patch)} bytes) from {base[:10]} — live now.")


def cmd_watch(args):
    print("Watching. Ctrl-C to stop.")
    last = None
    while True:
        current = tree_fingerprint(args.app)
        if current != last:
            last = current
            try:
                cmd_push(args)
            except SystemExit as e:
                # A failed push must not kill the watcher; the next save retries.
                print(f"push failed: {e}")
        time.sleep(args.interval)


def main():
    env_file = Path(os.environ.get("ONEAPP_FC_ENV", ROOT / ".fc.env"))
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "push", "revert", "watch"])
    parser.add_argument("--group", default=os.environ.get("ONEAPP_BENCH_GROUP", "bench-46799"))
    parser.add_argument("--app", default="oneapp_control")
    parser.add_argument("--assets", action="store_true", help="include the built SPA")
    parser.add_argument("--interval", type=int, default=20)
    args = parser.parse_args()

    {"status": cmd_status, "push": cmd_push, "revert": cmd_revert, "watch": cmd_watch}[
        args.command
    ](args)


if __name__ == "__main__":
    main()
