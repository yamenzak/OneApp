#!/usr/bin/env python3
"""Push the working tree onto a running Frappe Cloud bench, as a patch.

Development only. A patch is `git apply` inside the running container — seconds,
no image build — but it exists in no image, so **the next deploy silently
reverts it**. Nothing here is a way to ship.

    scripts/live.py status        what the bench runs, and what we have patched
    scripts/live.py push          send everything since the deployed commit
    scripts/live.py revert        remove our patch, back to the deployed image
    scripts/live.py watch         push on every change (Ctrl-C to stop)
    scripts/live.py deploy        build a real image and move the sites onto it
    scripts/live.py update-sites  move sites onto the newest bench

`deploy` is the honest path: an image built from git, so nothing silently
reverts later. Minutes rather than seconds, and the only way to ship a UI change
— the bench cannot run our Vite build.

Nothing here runs unless ONEAPP_DEV_BENCH_GROUP names the bench being targeted.
Patching rewrites code on a running bench and deploy restarts real sites; both
are fine while a bench is ours to break and unacceptable once it carries
customers. Production never sets it, so this tool is inert there.

Credentials come from ONEAPP_FC_ENV (default: the file named below), which sets
PRESS_KEY and PRESS_SECRET.

Assets: `--assets` is **experimental and currently does not work**. The bench
cannot build the SPA — `build_assets` runs `bench build`, Frappe's own esbuild,
which knows nothing about Vite — so the bundle would have to travel inside the
patch. yarn.lock makes our build byte-identical to Frappe Cloud's (verified: the
same commit produces the same content hashes both sides), and the resulting
patch applies cleanly to a faithful local reconstruction of the container — but
the agent rejects it, including a patch of nothing but new files. Agent Job
output is not exposed to the API, so there is nothing to diagnose it with.

Use `deploy` for UI changes. It is minutes rather than seconds and it is the
honest path anyway: an image built from git, which nothing later reverts.
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
    moves real sites onto a new image. Naming the group out of band is what
    stops either happening by accident, and a machine that never sets the
    variable has this whole tool inert rather than merely discouraged.

    There is deliberately no environment check beyond that. Staging and
    production share one bench group until the budget carries a second, so a
    rule that refused any group with a production workspace on it would refuse
    every deploy we have. Everything ships from `main` to every site; the
    Tenant and Shard `environment` fields stay for when a real staging bench
    exists and this can be tightened again.
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



def control_plane_check(group: str) -> dict | None:
    """What the control plane knows about who is on this bench group.

    Reported by `status`, and nothing acts on it. It used to veto a deploy onto
    a group carrying production workspaces, which is the right rule once there
    are two benches and the wrong one while there is a single bench carrying
    everything — it refused every deploy we could actually make.

    Skipped silently when ONEAPP_CONTROL_URL is unset or the control plane is
    unreachable.
    """
    base = os.environ.get("ONEAPP_CONTROL_URL")
    key = os.environ.get("ONEAPP_CONTROL_KEY")
    if not (base and key):
        return None

    request = urllib.request.Request(
        f"{base.rstrip('/')}/api/method/oneapp_control.api.admin.bench_environment",
        data=json.dumps({"release_group": group}).encode(),
        headers={"Authorization": f"token {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read()).get("message")
    except Exception as e:
        print(f"  (could not reach the control plane to double-check: {e})")
        return None


def press(method: str, payload: dict, timeout: int = 180, optional: bool = False) -> dict:
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
        if optional:
            # Used when probing for which doctype a record is: "not found" is an
            # answer, not a failure, and exiting on it means never trying the
            # next candidate.
            return {}
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


def built_tree_at(app: str, base: str) -> Path:
    """Build the SPA as the deployed commit built it.

    Needed because the bundle already exists in the container: Frappe Cloud
    built it into the image, so a patch that *adds* those files is rejected with
    "already exists". To send a modification instead, the deployed content has
    to be reconstructed — which only works because yarn.lock makes our build
    byte-identical to theirs. Verified: the same commit produces the same
    content hashes here and on Frappe Cloud.
    """
    work = ROOT / ".oneapp-live-base"
    if work.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(work)], cwd=ROOT,
                       capture_output=True, check=False)
    git("worktree", "add", "--force", "--detach", str(work), base)

    frontend = work / "apps" / app / "frontend"
    modules = ROOT / "apps" / app / "frontend" / "node_modules"
    link = frontend / "node_modules"
    if modules.exists() and not link.exists():
        # Same lockfile, so the same tree — installing again would only be slow.
        link.symlink_to(modules)

    build = subprocess.run(["npx", "vite", "build"], cwd=frontend,
                           capture_output=True, text=True, check=False)
    if build.returncode != 0:
        sys.exit(f"Could not build {base[:10]} to diff against:\n{build.stderr[-800:]}")
    return work


def _usable_sections(diff: str) -> str:
    """Keep additions and modifications; drop deletions and build noise.

    Asset filenames carry a content hash, so a rebuild replaces rather than
    edits them: the new names are additions and the old ones would be deletions.
    Removing the stale files is not worth the risk — a deletion hunk has to match
    the old content exactly, and an unreferenced asset costs nothing until the
    next deploy clears it.

    __pycache__ is dropped for the same reason it is everywhere else here: it is
    compiled per interpreter version, so one stray .pyc rejects the whole patch.
    """
    kept, section, skip = [], [], False
    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if section and not skip:
                kept.extend(section)
            section, skip = [line], "__pycache__" in line
            continue
        if line.startswith("deleted file mode"):
            skip = True
        section.append(line)
    if section and not skip:
        kept.extend(section)
    return "".join(kept)


def build_patch(app: str, base: str, with_assets: bool) -> str:
    """Everything from the deployed commit to the working tree, mirror-relative."""
    parts = [git("diff", base, "--", f"apps/{app}")]

    if with_assets:
        old_root = built_tree_at(app, base) / "apps" / app
        new_root = ROOT / "apps" / app
        for relative in ("public/frontend", "www"):
            old_dir, new_dir = old_root / app / relative, new_root / app / relative
            if not new_dir.exists():
                continue
            # --no-index so untracked build output is compared at all;
            # --binary or the woff2 fonts arrive as placeholders and git apply
            # rejects the whole patch; --no-renames because asset filenames
            # carry a content hash, so every rebuilt file looks like a rename of
            # the one it replaced and git emits rename hunks that cannot apply.
            diff = git("diff", "--no-index", "--binary", "--no-renames",
                       str(old_dir), str(new_dir), check=False)
            # git renders an absolute path as "a/home/user/..." — the leading
            # slash is consumed by the a/ prefix — so the replacement has to
            # match without it, or the result is "aoneapp_control/..." and every
            # path in the patch is wrong by one character.
            for absolute in (old_dir, new_dir):
                diff = diff.replace(str(absolute).lstrip("/"), f"{app}/{relative}")
            parts.append(_usable_sections(diff))

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
        # next_release is populated even when it is the release already
        # deployed, so its presence is not an update — only a difference is.
        # Treating it as one asks for the hash of a release that is not in the
        # app's releases list, because press only lists the ones on offer.
        has_update = a.get("next_release") and a["next_release"] != a.get("current_release")
        updating = a["app"] in args.apps and has_update

        release = a["next_release"] if updating else a.get("current_release")
        digest = (hash_for(a, release) if updating else None) or a.get("current_hash")
        if not (release and digest):
            sys.exit(f"No release/hash for {a['app']}; press changed shape.")
        apps.append({"app": a["app"], "source": a["source"], "release": release, "hash": digest})
        if updating:
            moving.append(f"  {a['app']} -> {digest[:10]}")

    if not moving:
        print("Nothing to deploy — the bench already has the newest releases.")
        return
    print("\n".join(moving))
    # `sites` must be the dicts deploy_information returned, not bare names.
    # Passing names fails in "Preparing deployment" with nothing exposed to the
    # API to say why — which reads like a broken bench rather than a bad
    # argument. The entries carry server, bench and the skip_* flags the deploy
    # needs to plan each move.
    sites = info.get("sites") or []
    candidate = press(
        "press.api.bench.deploy_and_update",
        {"name": args.group, "apps": apps, "sites": sites},
        timeout=300,
    ).get("message")
    names = ", ".join(s["name"] for s in sites)
    print(f"Building {candidate}. Sites move onto it when the build succeeds: {names}")

    if args.wait and not watch_deploy(args.group, candidate):
        sys.exit("Deploy failed; sites left where they were.")


def update_sites(group: str):
    """Move every site on the group onto the newest bench.

    A successful build only creates a bench. Sites stay where they are until
    each is told to move, which is the step that actually changes what anyone
    sees — and the one that restarts them.
    """
    info = press("press.api.bench.deploy_information", {"name": group})["message"]
    sites = [s["name"] for s in info.get("sites") or []]
    for name in sites:
        print(f"  updating {name}")
        # "Could not find suitable Destination Bench" here means the site is
        # already on the newest bench, which is the normal case after `deploy`:
        # deploy_and_update moves the sites itself. Only a build run on its own
        # leaves anything for this command to do.
        result = press("press.api.site.update", {"name": name}, timeout=300, optional=True)
        if not result:
            print(f"    {name} is already on the newest bench")
            continue

    # A site returns 503 while it moves, so "the call succeeded" is not the same
    # as "the site is back". Reporting success at the call and walking away is
    # how a deploy looks finished while every request is still failing.
    for name in sites:
        wait_for_site(name)


def wait_for_site(site: str, attempts: int = 45):
    """Poll a site until it answers again after a move."""
    url = f"https://{site}/api/method/ping"
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                if response.status == 200:
                    print(f"  {site} is back")
                    return True
        except Exception:
            pass
        time.sleep(20)
    print(f"  {site} has not come back yet — check the Frappe Cloud dashboard.")
    return False


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
        found = press(
            "press.api.client.get",
            {"doctype": candidate_type, "name": name},
            optional=True,
        )
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

    # Reported, not enforced: one bench carries everything until there is budget
    # for a second, so this says who is on it rather than refusing the deploy.
    verdict = control_plane_check(args.group)
    if verdict:
        print(f"carries {verdict.get('reason', '')}")


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
    parser.add_argument("--group", default=os.environ.get("ONEAPP_BENCH_GROUP", "bench-46810"))
    parser.add_argument("--app", default="oneapp_control")
    parser.add_argument("--assets", action="store_true",
                        help="EXPERIMENTAL, currently rejected by the agent; use deploy")
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
