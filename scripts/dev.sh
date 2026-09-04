#!/usr/bin/env bash
#
# The fast loop.
#
# Frappe Cloud is where tenants run, not where we develop. A change pushed there
# rebuilds a bench image and then moves sites onto it — minutes per edit, and it
# is the wrong tool for "does this button work". This runs the control site
# locally instead, with the monorepo symlinked into the bench, so a Python edit
# is live on the next request and an SPA edit is live before you look up.
#
#   scripts/dev.sh up        start MariaDB, Redis and the Frappe web server
#   scripts/dev.sh worker    a background worker, for anything that enqueues
#   scripts/dev.sh spa       Vite dev server for an SPA (hot reload, own port)
#   scripts/dev.sh watch     rebuild an SPA into public/ as you edit it
#   scripts/dev.sh shell     a Python REPL bound to the site
#   scripts/dev.sh run FILE  execute a Python file against the site
#   scripts/dev.sh seed      the dev fixture (--manifest for the fast half)
#   scripts/dev.sh down      stop the web server
#
# There are two SPAs and therefore two sites. ONEAPP_SITE and ONEAPP_PORT pick
# which, and the pid file is named after the port so both can run at once:
#
#   scripts/dev.sh up                                    OneAdmin, :8000
#   ONEAPP_SITE=space.localhost ONEAPP_PORT=8001 \
#     scripts/dev.sh up                                  OneSpace, :8001
#
# Nothing here touches Frappe Cloud.

set -euo pipefail

BENCH="${ONEAPP_BENCH:-/home/frappe/bench1}"
SITE="${ONEAPP_SITE:-control.localhost}"
PY="$BENCH/env/bin/python"
PORT="${ONEAPP_PORT:-8000}"
# Per port, not per bench: one pid file for both sites means starting the second
# server orphans the first, and `down` then reports success while something is
# still listening.
PIDFILE="$BENCH/.oneapp-dev-$PORT.pid"

sites_path="$BENCH/sites"

require_bench() {
  [ -x "$PY" ] || { echo "No python at $PY. Is ONEAPP_BENCH right?" >&2; exit 1; }
  [ -d "$sites_path/$SITE" ] || { echo "No site $SITE under $sites_path." >&2; exit 1; }
  # Everything Frappe resolves relatively is relative to the *sites directory*,
  # which is why bench runs from there. Two of them bite immediately:
  #   - logs go to realpath("..")/logs, i.e. the bench root
  #   - the asset manifest is read as "assets/assets.json"
  # Run from the bench root instead and the manifest is silently missing, which
  # surfaces as a 500 raised inside the exception handler pointing at a Jinja
  # include — nothing about a path. So pin the cwd rather than debug it twice.
  cd "$sites_path"
  mkdir -p "$BENCH/logs"
}

services() {
  pgrep -x mariadbd >/dev/null || service mariadb start >/dev/null 2>&1 || true
  # Ports come from common_site_config.json; starting them idempotently is
  # cheaper than parsing it and checking each one.
  for port in 11000 13000; do
    redis-cli -p "$port" ping >/dev/null 2>&1 || redis-server --port "$port" --daemonize yes
  done

  # Realtime. Without it the SPA's socket retries forever against a path Frappe
  # answers with the SPA's own HTML, so the console fills with JSON parse errors
  # that look like an application bug and are not — and live updates silently
  # never arrive.
  # Checked by port, not by pgrep: `pgrep -f socketio.js` also matches the
  # shell command that contains the string, so it reports the server running
  # when nothing is.
  #
  # `setsid`, and it is not decoration. `( … & )` leaves the node process a
  # child of this script — it is orphaned by the subshell and immediately
  # re-parented back — so bash sits in `wait4` for it and the script never
  # exits. Every command that calls `services` and is not itself a server then
  # hangs forever *after doing its work*: `dev.sh migrate` ran the whole
  # migration in ninety seconds and then held the terminal for an hour, which
  # reads exactly like a migration that is still going.
  #
  # `setsid` puts it in a session of its own, where it cannot be waited on.
  if ! (exec 3<>/dev/tcp/127.0.0.1/9000) 2>/dev/null; then
    setsid nohup node "$BENCH/apps/frappe/socketio.js" \
      >"$BENCH/logs/socketio.log" 2>&1 < /dev/null &
    disown 2>/dev/null || true
    sleep 2
  fi
}

case "${1:-up}" in
  up)
    require_bench
    # Both of these come before `services`, because they decide what the
    # socketio server has to be started with.
    #
    # The site by its own hostname: Frappe's socketio server works out which
    # site a connection belongs to from the Origin header and refuses a
    # namespace that does not match — so on `localhost` every socket comes back
    # "Invalid namespace" and realtime is silently off. Node does not resolve
    # `*.localhost` the way a browser does, so the entry has to be real.
    if ! getent hosts "$SITE" >/dev/null 2>&1; then
      if [ -w /etc/hosts ]; then
        echo "127.0.0.1 $SITE" >> /etc/hosts
        echo "Added $SITE to /etc/hosts, so the socket can name its site."
      else
        echo "warning: $SITE does not resolve and /etc/hosts is not writable."
        echo "         Realtime will be off; add '127.0.0.1 $SITE' by hand."
      fi
    fi

    # And the port the socketio server calls back to. It authenticates a
    # connection by asking the site who the cookie belongs to, and in developer
    # mode it builds that URL from the origin with `webserver_port` swapped in
    # — unset on this bench, so every socket failed against a URL ending in
    # `:undefined`. One bench-wide setting for two sites on two ports: whoever
    # started last owns realtime, which is the right answer for a dev loop
    # driving one site at a time.
    if "$PY" - "$sites_path" "$PORT" <<'PYEOF'
import json
import os
import sys

sites_path, port = sys.argv[1], int(sys.argv[2])
path = os.path.join(sites_path, "common_site_config.json")
with open(path) as fh:
    conf = json.load(fh)
if conf.get("webserver_port") == port:
    sys.exit(1)
conf["webserver_port"] = port
with open(path, "w") as fh:
    json.dump(conf, fh, indent=1)
    fh.write("\n")
print(f"webserver_port set to {port}, so realtime can authenticate.")
PYEOF
    then
      # The socketio server reads the config once, at startup. A running one is
      # holding the old port, so it goes and `services` starts a fresh one.
      pkill -f "node apps/frappe/socketio.js" 2>/dev/null || true
      sleep 1
    fi

    services
    mkdir -p "$BENCH/logs"
    echo "Serving $SITE on http://$SITE:$PORT"
    "$PY" - "$sites_path" "$SITE" "$PORT" <<'PYEOF' &
import sys

import frappe.app

sites_path, site, port = sys.argv[1], sys.argv[2], int(sys.argv[3])

# frappe.app.serve is the supported entry, and using it matters for more than
# tidiness: it also mounts the /assets and /files static middleware. Calling
# run_simple on the bare WSGI app skips those, so every page loads but no
# stylesheet or bundle does.
#
# `site` pins the request to one site. Without it Frappe resolves the site from
# the Host header, so localhost:8000 looks for a site literally named
# "localhost" and 404s with "localhost does not exist" — which reads like the
# site is broken rather than like the URL is.
frappe.app.serve(
    port=port,
    site=site,
    sites_path=sites_path,
    # The reloader's child is orphaned when the launching shell detaches, which
    # leaves nothing listening and no error to explain it. `dev.sh restart` is
    # one command, and a Python edit needs a restart either way.
    no_reload=True,
    bind_addr="0.0.0.0",
)
PYEOF
    echo $! > "$PIDFILE"
    ;;

  worker)
    require_bench
    services
    # A background worker, in the foreground of this shell.
    #
    # `dev.sh up` starts a web server and nothing else, which is right for
    # almost everything: a request is served in the request. It is wrong for
    # anything that reaches `frappe.enqueue`, and that is a longer list than it
    # sounds — every notification the framework produces is enqueued, so on a
    # bench with no worker a mention or an assignment writes nothing at all and
    # the panel is empty for a reason that looks like our bug.
    #
    # RQ's own worker rather than `bench worker`: bench reads its config from
    # the directory it is run in, and this script is deliberately runnable from
    # anywhere.
    exec "$PY" -c "
import frappe
from frappe.utils.background_jobs import start_worker

frappe.init(site='$SITE', sites_path='$sites_path')
print('Working the queues for $SITE. Ctrl-C to stop.')
start_worker(queue='${2:-default}')
"
    ;;

  spa)
    cd "$(dirname "$0")/../apps/${2:-oneapp_control}/frontend"
    # frappe-ui's plugin proxies /api, /assets and /files to the bench it finds
    # in common_site_config.json, so the SPA talks to the local site with no
    # CORS and the real session cookie.
    exec npx vite --host
    ;;

  watch)
    # The bundle, rebuilt into the app's public/ as you edit it.
    #
    # Thirteen seconds per rebuild against twenty-two for a cold `vite build`,
    # measured. Not the second-or-two an HMR server gives: `vite build --watch`
    # is Rollup re-bundling, so it walks the whole graph again and only saves
    # the cold start. It is still the right tool here, because it writes to the
    # same `public/frontend` the bench already serves — so a screenshot, a spec
    # and curl all see the change at the same URL, with the same session.
    #
    # `spa` above is the sub-second loop and does not currently reach the
    # OneSpace site: frappe-ui's plugin finds the bench through
    # `common_site_config.json` relative to the frontend, and this repo is
    # symlinked *into* the bench rather than sitting under it, so it falls back
    # to port 8000 and proxies to the wrong site. Worth fixing; not fixed.
    #
    #   scripts/dev.sh watch oneapp     &   # once, in the background
    #   cd apps/oneapp/frontend && yarn shot '/one/space/rua'
    cd "$(dirname "$0")/../apps/${2:-oneapp}/frontend"
    exec npx vite build --watch
    ;;

  shell)
    require_bench
    services
    exec "$PY" -i -c "
import frappe
frappe.init(site='$SITE', sites_path='$sites_path')
frappe.connect()
print('Bound to $SITE. frappe.db is live; nothing commits until frappe.db.commit().')
"
    ;;

  run)
    [ -n "${2:-}" ] || { echo "usage: dev.sh run FILE [ARG...]" >&2; exit 1; }
    # Resolved before require_bench, which cds to the sites directory: a
    # relative path handed in from the repo would otherwise not exist by the
    # time python opens it, and the error names the file rather than the cd.
    script="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
    require_bench
    services
    # Anything after the file is the script's own, and it arrives as the
    # script's `sys.argv` rather than as this wrapper's. Without that a script
    # reading a flag sees `["-", sites_path, site, path]` — every flag it looks
    # for missing, and every one it does not look for possibly present.
    "$PY" - "$sites_path" "$SITE" "$script" "${@:3}" <<'PYEOF'
import sys
import frappe

sites_path, site, path = sys.argv[1], sys.argv[2], sys.argv[3]
# argv[0] is the script, as it would be if python had been handed the file, so
# `sys.argv[1:]` inside it means what it means everywhere else.
sys.argv = [path, *sys.argv[4:]]
frappe.init(site=site, sites_path=sites_path)
frappe.connect()
try:
    exec(compile(open(path).read(), path, "exec"), {"frappe": frappe, "__name__": "__main__"})
finally:
    # Explicit: a script that raised should not half-commit, and one that
    # succeeded should not silently lose its writes.
    frappe.db.commit()
    frappe.destroy()
PYEOF
    ;;

  seed)
    # The fixture, by name rather than by path — it is run often enough that
    # remembering where it lives is friction nobody needs.
    #
    #   dev.sh seed              everything, and sweep up after the last pass
    #   dev.sh seed --manifest   re-declare the spaces, and stop
    #
    # The second is the one to reach for while iterating on a screen or a
    # theme: it writes the half a manifest edit changes and skips the half it
    # does not, which is seconds rather than minutes. Run the full one before
    # a browser pass, because only the full one sweeps up after the last.
    exec "$0" run "$(dirname "$0")/seed_dev_space.py" "${@:2}"
    ;;

  build)
    # Frappe's own web assets — the login page and anything server-rendered.
    # Our SPAs do not need this: Vite builds them straight into the app's
    # public/ directory. Needed once, and again after pulling frappe.
    #
    # frappe develop requires Node >= 24. On anything older yarn refuses the
    # install with an engine error and leaves node_modules empty, so the build
    # then fails with MODULE_NOT_FOUND — which points at the wrong problem.
    node_bin="${ONEAPP_NODE:-/opt/node24/bin}"
    cd "$BENCH/apps/frappe"
    PATH="$node_bin:$PATH" yarn install
    PATH="$node_bin:$PATH" SITES_PATH="$sites_path" node esbuild --production --apps frappe
    ;;

  login)
    # A session cookie without touching the login page, so the API is usable
    # from curl while iterating.
    require_bench
    curl -s -c "$BENCH/.oneapp-cookies" -X POST \
      -d "usr=${2:-Administrator}&pwd=${3:-admin}" \
      "http://localhost:$PORT/api/method/login"
    echo
    echo "Cookie jar: $BENCH/.oneapp-cookies"
    echo "Use it with: curl -b $BENCH/.oneapp-cookies http://localhost:$PORT/api/method/..."
    ;;

  migrate)
    require_bench
    services
    # Frappe's develop branch moves its own schema, so a site left alone for a
    # week fails with "DocType X not found" on a page that has nothing to do
    # with X. Run this after pulling frappe, or after adding a doctype here.
    "$PY" - "$sites_path" "$SITE" <<'PYEOF'
import sys
import frappe
from frappe.migrate import SiteMigration

sites_path, site = sys.argv[1], sys.argv[2]
frappe.init(site=site, sites_path=sites_path)
SiteMigration(skip_failing=False).run(site=site)
PYEOF
    ;;

  restart)
    "$0" down >/dev/null 2>&1 || true
    exec "$0" up
    ;;

  down)
    # The pid file is a hint, not the truth. It is written by whichever shell
    # launched the server, so a `nohup ... &` from a script, a container
    # restart, or a second `up` all leave it stale — and then `down` prints
    # "not running" while something is still listening, the next `up` dies with
    # "Address already in use" into a log nobody is reading, and every request
    # is answered by the *old* code. That failure costs an hour every time,
    # because everything looks fine and only the behaviour is old. So ask the
    # port who has it.
    stopped=""
    if [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null; then
      stopped="yes"
    fi
    rm -f "$PIDFILE"
    holder="$(ss -lptnH "sport = :$PORT" 2>/dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)"
    if [ -n "$holder" ] && kill "$holder" 2>/dev/null; then
      stopped="yes"
    fi
    [ -n "$stopped" ] && echo "stopped" || echo "not running"
    ;;

  *)
    sed -n '3,20p' "$0"
    exit 1
    ;;
esac
