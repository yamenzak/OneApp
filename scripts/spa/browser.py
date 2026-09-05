"""The browser pass: Playwright, and the screenshot command.

Both SPAs get one, because the bugs it catches — an empty list, a dialog that
will not open, a panel unreachable at one viewport — all render without throwing,
so a clean build says nothing about them. `shot.mjs` is the four-second way to
look at a page without writing a script to do it.
"""

from .spec import BANNER


def playwright_config(app: str, spec: dict) -> str:
    return BANNER + """
// Visual checks against a real local site, not a mocked one.
//
// The bugs this exists to catch — an empty list, a dialog that will not open, a
// control unreachable at one viewport — all render without throwing, so unit
// tests and a clean build say nothing about them. Only looking does.
//
// Start the site this points at first:
//   ONEAPP_SITE=%(site)s ONEAPP_PORT=%(port)d scripts/dev.sh up
import { defineConfig, devices } from '@playwright/test'

// The image ships one Chromium build and this runner expects another;
// `playwright install` is disabled here, so point at what exists rather than
// letting it try to download a build it will never get.
const CHROMIUM =
  process.env.ONEAPP_CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const launchOptions = { executablePath: CHROMIUM }

export default defineConfig({
  testDir: './e2e',
  // One worker, for two reasons that are easy to mistake for one.
  //
  // The first is correctness. Every spec drives the *same* seeded space and
  // several write the same record — a comment count, an assignment, a rename,
  // a heart. At four workers six specs fail on data another worker moved:
  // child-table, follow, import, realtime, record-surface and space. That is a
  // suite that is faster and no longer tells the truth.
  //
  // The second is that the speed is not there anyway. This machine has four
  // cores and the site is one GIL-bound Python process, so the browsers and
  // the server contend for the same four. Measured rather than assumed: the
  // desktop project is 3.5 minutes at four workers against about 4.75 at one,
  // and concurrent API calls plateau at 1.9x by two-way concurrency.
  //
  // So the honest fix is a seeded space per worker keyed on `parallelIndex`,
  // and even that returns under 2x here. It is not a config change and it is
  // not the biggest win available — that one is not running all 260 of these
  // for a change that touched three files.
  //
  // While iterating, run the specs you are changing:
  //   npx playwright test theme.spec.js --project=desktop
  // `yarn e2e:fast` is the same idea with the parallelism turned up, for a
  // handful of read-only specs. `yarn e2e` before a commit.
  workers: Number(process.env.ONEAPP_E2E_WORKERS || 1),
  reporter: [['list']],
  // Retried once, and only the retry is traced. `retain-on-failure` records
  // every test and throws away all but the failures, which is a tax on the
  // ninety-nine that pass to keep the one that does not.
  retries: 1,
  timeout: 45_000,
  use: {
    // The site by its own hostname, not `localhost`. Frappe's socketio server
    // works out which site a socket belongs to from the Origin header and
    // refuses a namespace that does not match it — so on `localhost` every
    // connection came back "Invalid namespace" and realtime was silently off
    // for the whole browser pass. `*.localhost` resolves without a hosts file
    // entry, and this is also how the site is addressed in production.
    baseURL: process.env.ONEAPP_BASE_URL || 'http://%(site)s:%(port)d',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], launchOptions } },
    // The screenshot that started this was a phone: no sidebar, so anything
    // that lives only there is unreachable.
    { name: 'mobile', use: { ...devices['Pixel 7'], launchOptions } },
  ],
})
""" % {"site": spec["site"], "port": spec["port"]}


SHOT_MJS = BANNER + r"""
/**
 * One screen, as a PNG. `yarn shot <path> [file.png]`.
 *
 * Looking at a change is the shortest question you can ask this product, and it
 * used to be one of the most expensive: sign in, drive the app to the screen,
 * wait for the rows, screenshot — twenty lines written from scratch every time
 * somebody wanted to see something, and got slightly wrong every time. The
 * login form rather than the endpoint. A fixed sleep rather than a wait. A
 * browser Playwright then tried to download.
 *
 *   yarn shot '/one/space/rua?screen=projects'
 *   yarn shot '/one/space/rua?screen=projects' rua.png --phone
 *   yarn shot '/one/space/rua?screen=projects' --wait='[data-slot="list-row"]'
 *   yarn shot '/one/mail' --click='text=Quotation' --wait='[data-slot="mail-body"]'
 *
 * `--wait` is the flag worth knowing: a selector to wait for before the
 * shutter. Without one this waits for the network to go quiet, which is right
 * for most screens and wrong for any that keeps a socket open. Give it the
 * thing you are actually looking at.
 *
 * `--click` is the other one: a selector to press after the page loads, before
 * the shutter. Half of what is worth photographing is a row deep — a mail
 * thread, an open record, a dialog — and without it the only way to reach any
 * of those was a throwaway Playwright script.
 *
 * The rest: `--phone` for the suite's phone viewport, `--full` for the whole
 * scrollable page, `--retina` when the detail is the point, `--settle=MS` for
 * an animation this does not know about.
 *
 * `--tokens=--a,--b` prints those CSS custom properties as the page resolves
 * them, which is the only way to check a *declared* look actually arrived: a
 * one-pixel tab indicator is a token you can read and a colour you cannot see
 * in a screenshot, and the difference between "the theme is wrong" and "the
 * line is thin" is otherwise an afternoon.
 *
 * Nothing here builds. `scripts/dev.sh watch` keeps the bundle current, so the
 * loop is edit, look — not edit, build, look.
 */
import { chromium } from '@playwright/test'
import { signIn } from './e2e/auth.js'
// The site, and the browser to open it with, read from the suite's own config
// rather than restated here. Both are things this environment gets wrong in a
// way that wastes an afternoon — the image ships one Chromium build and the
// runner expects another — and having the answer in two places is how one of
// them goes stale without anybody noticing.
import config from './playwright.config.js'

const args = process.argv.slice(2)
const flag = (name, fallback) => {
  const found = args.find((one) => one.startsWith(`--${name}=`))
  return found === undefined ? fallback : found.slice(name.length + 3)
}
const has = (name) => args.includes(`--${name}`)
const positional = args.filter((one) => !one.startsWith('--'))

const path = positional[0]
if (!path) {
  console.error(
    'usage: yarn shot <path> [out.png] ' +
      '[--wait=SELECTOR] [--click=SELECTOR] [--phone] [--full] [--retina] [--settle=MS] ' +
      '[--tokens=--a,--b]',
  )
  process.exit(1)
}
const out = positional[1] || 'shot.png'
const base = process.env.ONEAPP_BASE_URL || config.use.baseURL

// The project whose viewport this is, so what you look at is what the tests
// look at rather than a size chosen here.
const named = has('phone') ? 'mobile' : 'desktop'
const project = config.projects.find((one) => one.name === named) || config.projects[0]
const viewport = flag('width')
  ? { width: Number(flag('width')), height: Number(flag('height', 900)) }
  : project.use.viewport

const browser = await chromium.launch(project.use.launchOptions)
const context = await browser.newContext({
  viewport,
  // 1x by default: these get looked at and sent around, and a retina PNG is
  // four times the bytes for something somebody will glance at.
  deviceScaleFactor: has('retina') ? 2 : 1,
})
const page = await context.newPage()

// Said out loud afterwards, because a screenshot of a broken screen is not
// obviously a screenshot of a broken screen — it is usually just empty.
const complaints = []
page.on('pageerror', (e) => complaints.push(String(e)))
page.on('response', (r) => {
  if (r.status() >= 400) complaints.push(`${r.status()} ${r.url()}`)
})

try {
  await signIn(page, base)
  await page.goto(base + path)
  const click = flag('click')
  if (click) await page.locator(click).first().click({ timeout: 40_000 })
  const wait = flag('wait')
  if (wait) await page.locator(wait).first().waitFor({ timeout: 40_000 })
  else await page.waitForLoadState('networkidle').catch(() => {})
  // A beat for the last transition to land. Short, because `--wait` is the
  // right answer whenever it actually matters.
  await page.waitForTimeout(Number(flag('settle', 600)))
  await page.screenshot({ path: out, fullPage: has('full') })
  console.log(out)

  const asked = flag('tokens')
  if (asked) {
    const values = await page.evaluate((names) => {
      const style = getComputedStyle(document.documentElement)
      return names.map((one) => [one, style.getPropertyValue(one).trim()])
    }, asked.split(',').map((one) => one.trim()).filter(Boolean))
    for (const [name, value] of values) console.log(`${name}: ${value || '(unset)'}`)
  }
  if (complaints.length) {
    console.log('---')
    for (const one of [...new Set(complaints)].slice(0, 10)) console.log(one)
  }
} finally {
  await browser.close()
}
"""


def shot_mjs(app: str, spec: dict) -> str:
    """`yarn shot` for this bundle.

    Takes no substitution: the site and the browser come from
    `playwright.config.js`, which this bundle also generates.
    """
    return SHOT_MJS


E2E_AUTH_JS = BANNER + r"""
// Sign in through Frappe's own endpoint rather than the login form: the form is
// Frappe's, not ours, and driving it would make every test depend on markup we
// do not own.
//
// `who` names somebody other than the default, which the realtime tests need:
// some things only exist between two people, and Frappe will not tell you that
// *you* are the one looking at a record.
export async function signIn(page, baseURL, who = {}) {
  const response = await page.request.post(`${baseURL}/api/method/login`, {
    form: {
      usr: who.user || process.env.ONEAPP_USER || 'Administrator',
      pwd: who.password || process.env.ONEAPP_PASSWORD || 'Dev-Loop-2026!x',
    },
  })
  if (!response.ok()) {
    throw new Error(`login failed: ${response.status()} ${await response.text()}`)
  }
}

/**
 * Console errors and failed requests, because a page can be broken and silent.
 *
 * Failed requests are collected from the network rather than from the console.
 * The console message for one is "Failed to load resource: the server responded
 * with a status of 404 (NOT FOUND)" — no URL, nothing to tell a broken endpoint
 * from a route that only exists behind nginx. Reading the response gives the
 * URL, which is both a better failure message and the only way to ignore one
 * thing without ignoring everything.
 */
export function collectConsoleErrors(page) {
  const errors = []
  page.on('console', (m) => {
    // Dropped: the network hook below reports the same failure with its URL.
    if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) {
      errors.push(m.text())
    }
  })
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('response', (r) => {
    if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`)
  })
  return errors
}

/**
 * Fail on errors that mean something is broken, not on noise.
 *
 * The one worth catching is a fetch whose body is HTML: under our SPA route
 * rules Frappe answers an unknown path with the app's own page at 200, so a
 * mis-built request URL never 404s — it quietly returns a document and the data
 * is simply absent. That is how every useResource call fetched nothing.
 */
const NL = String.fromCharCode(10)

export function expectNoRealErrors(errors) {
  const ignorable = [
    // Logged by frappe-ui during a brief window before a resource resolves;
    // renders correctly and does not throw. Tracked, not silenced everywhere.
    /reading 'charAt'/,
    // A print preview is rendered into a `sandbox=""` iframe on purpose: a
    // print format is HTML somebody in the workspace wrote, and a preview is
    // not a place to run it. Chromium says so once per script the format
    // carries, which is the sandbox working rather than anything failing.
    /Blocked script execution in 'about:/,
    // Realtime is proxied to the socketio port by nginx in production. The
    // development server serves the built SPA with no proxy in front of it, so
    // this 404s locally and only locally — and it did so on every page, which
    // meant this whole check was passing nothing. Realtime is therefore not
    // covered by the browser pass; it is exercised on a real site.
    /\/socket\.io\//,
    // A request the browser cancelled, which is what `fetch` reports when the
    // page navigates out from under one. The Mail screen refetches on a
    // realtime event, so any spec that reloads shortly after acting on a
    // message can lose that refetch mid-flight — and losing it is correct
    // behaviour, not a failure. A server that really fails answers with a
    // status, which the response listener above still catches.
    /TypeError: Failed to fetch/,
  ]
  const real = errors.filter((e) => !ignorable.some((p) => p.test(e)))
  if (real.length) {
    throw new Error('console errors:' + NL + real.join(NL))
  }
}
"""
