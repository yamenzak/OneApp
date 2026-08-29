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


def require_dev_bench(group: str):
    """Refuse to touch anything that has not been named as the dev bench.

    Everything in this file rewrites code on a *running* bench, and `deploy`
    moves real sites onto a new image. Both are fine while a bench is ours to
    break and unacceptable once it carries customers, and the difference is not
    something a script can infer — so it is stated once, out of band, and
    nothing here runs without it.

    Production simply never sets ONEAPP_DEV_BENCH_GROUP, which makes this whole
    tool inert there rather than merely discouraged.
    """
    allowed = os.environ.get("ONEAPP_DEV_BENCH_GROUP")
    if not allowed:
        sys.exit(
            "ONEAPP_DEV_BENCH_GROUP is not set. This tool patches and deploys "
            "onto a running bench, so it only works on a bench you have named "
            "as a development one. Set it to the group you are developing on."
        )
    if allowed != group:
        sys.exit(
            f"Refusing to touch {group}: ONEAPP_DEV_BENCH_GROUP names {allowed}."
        )


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


def cmd_deploy(args):
    """Pull the newest releases, build an image, and move the sites onto it.

    The proper path, not a patch: an image built from git, so nothing silently
    reverts later. Minutes rather than seconds, which is why `push` exists — but
    UI changes need this, because the bench cannot run our Vite build.
    """
    require_dev_bench(args.group)

    # A live patch would be reverted by the deploy anyway; clearing it first
    # keeps our state file honest rather than pointing at a patch that is gone.
    if read_state().get("app_patch"):
        print("Reverting the live patch first — a deploy would drop it anyway.")
        cmd_revert(args, quiet=True)

    # Ask GitHub for anything pushed since press last looked, or the deploy
    # builds whatever it already knew about and appears to do nothing.
    for app in args.apps:
        press("press.api.bench.fetch_latest_app_update", {"name": args.group, "app": app})

    info = press("press.api.bench.deploy_information", {"name": args.group})["message"]
    if info.get("deploy_in_progress"):
        sys.exit("A deploy is already running on this bench.")

    # There is no next_hash beside next_release: press returns hashes inside the
    # app's own releases list, keyed by release name. Sending the wrong shape is
    # rejected by validate_app_hashes, so this has to be looked up.
    def hash_for(app_entry, release):
        for candidate in app_entry.get("releases") or []:
            if candidate.get("name") == release:
                return candidate.get("hash")
        return None

    # Every app on the bench, not just the ones being updated. A deploy builds a
    # whole image, so a partial list produces a candidate missing frappe itself
    # and fails in "Preparing deployment" with nothing exposed to the API.
    # Apps not being updated are pinned to what they already run.
    apps, moving = [], []
    for a in info["apps"]:
        updating = a["app"] in args.apps and a.get("next_release")
        release = a["next_release"] if updating else a.get("current_release")
        digest = hash_for(a, release) if updating else a.get("current_hash")
        if not (release and digest):
            sys.exit(f"No release/hash for {a['app']}; press changed shape.")
        apps.append({"app": a["app"], "source": a["source"], "release": release, "hash": digest})
        if updating:
            moving.append(f"  {a['app']} -> {digest[:10]}")

    if not moving:
        print("Nothing to deploy — the bench already has the newest releases.")
        return
    print("\n".join(moving))
    # Two calls, not deploy_and_update. On this account deploy_and_update runs
    # the newer Release Pipeline flow, which failed in "Preparing deployment"
    # with no detail exposed to the API; bench.deploy builds the same image and
    # works. Splitting them is also honest about what each half does — a build
    # changes nothing a customer sees until a site is moved onto it.
    candidate = press(
        "press.api.bench.deploy", {"name": args.group, "apps": apps}, timeout=300
    ).get("message")
    print(f"Building {candidate}.")

    if not args.wait:
        print("Sites stay on the old bench until this finishes — rerun with --wait "
              "to move them, or use `update-sites` afterwards.")
        return

    if not watch_deploy(args.group, candidate):
        sys.exit("Build failed; sites left where they were.")
    update_sites(args.group)


def update_sites(group: str):
    """Move every site on the group onto the newest bench.

    A successful build only creates a bench. Sites stay where they are until
    each is told to move, which is the step that actually changes what anyone
    sees — and the one that restarts them.
    """
    info = press("press.api.bench.deploy_information", {"name": group})["message"]
    for site in info.get("sites") or []:
        name = site["name"]
        print(f"  updating {name}")
        press("press.api.site.update", {"name": name}, timeout=300)
    print("Sites are moving; each restarts as it lands.")


def cmd_update_sites(args):
    require_dev_bench(args.group)
    update_sites(args.group)


def watch_deploy(group: str, name: str):
    """Follow a build to its end. Long by nature — an image is being built.

    Follows the record `deploy_and_update` returned, not the bench's generic
    deploy_in_progress flag: that flag is false for the first few seconds, so
    watching it reports the *previous* deploy's result and calls it done.

    Which record it is depends on the account. With Press Settings'
    use_new_deploy_flow on, deploy_and_update returns a Release Pipeline; the
    older path returns a Deploy Candidate.
    """
    doctype = None
    # Three possible record types, depending on the account and the endpoint:
    # bench.deploy returns a Deploy Candidate Build here, deploy_and_update
    # returns a Release Pipeline where the newer flow is on, and older accounts
    # return a Deploy Candidate. Guessing wrong silently follows nothing.
    for candidate_type in ("Deploy Candidate Build", "Release Pipeline", "Deploy Candidate"):
        found = press("press.api.client.get", {"doctype": candidate_type, "name": name})
        if found.get("message"):
            doctype = candidate_type
            break
    if not doctype:
        print(f"Cannot follow {name}; check the Frappe Cloud dashboard.")
        return False

    for _ in range(180):
        doc = press("press.api.client.get", {"doctype": doctype, "name": name})["message"]
        status = doc.get("status")
        if status in ("Success", "Failure", "Failed"):
            print(f"{doctype} {name}: {status}")
            if status != "Success":
                for stage in (doc.get("steps") or {}).get("stages", []):
                    print(f"  {stage.get('label')}: {stage.get('status')}")
            return status == "Success"
        print(f"  {status or 'running'}...")
        time.sleep(20)
    print("Still building. Check the Frappe Cloud dashboard.")
    return False


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
    require_dev_bench(args.group)
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
    require_dev_bench(args.group)
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
    parser.add_argument("command", choices=["status", "push", "revert", "watch", "deploy", "update-sites"])
    parser.add_argument("--group", default=os.environ.get("ONEAPP_BENCH_GROUP", "bench-46799"))
    parser.add_argument("--app", default="oneapp_control")
    parser.add_argument("--assets", action="store_true", help="include the built SPA")
    parser.add_argument("--interval", type=int, default=20)
    parser.add_argument("--apps", nargs="+", default=["oneapp_control", "oneapp"],
                        help="apps to deploy (deploy only)")
    parser.add_argument("--wait", action="store_true", help="follow the build (deploy only)")
    args = parser.parse_args()

    {
        "status": cmd_status,
        "push": cmd_push,
        "revert": cmd_revert,
        "watch": cmd_watch,
        "deploy": cmd_deploy,
        "update-sites": cmd_update_sites,
    }[args.command](args)


if __name__ == "__main__":
    main()
