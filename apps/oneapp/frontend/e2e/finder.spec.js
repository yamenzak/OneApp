// The one box over every space, which is a keyboard surface and therefore
// invisible to everything else.
//
// `check_screens.py` opens routes and this has none: it is a dialog bound to
// Ctrl+K, it renders over whatever page is showing, and the half of it that
// matters most — the screens — comes out of the session payload rather than
// off the wire. Nothing else in the suite would notice it going quiet.
//
// Four things are checked here and each has failed once in the making:
//
//   * the shortcut works *while the caret is in a box*, which is the one
//     place `lib/shell/shortcuts.js` deliberately stands down;
//   * the list is useful before anything is typed, and it is the space you are
//     standing in rather than the first eight screens of the workspace;
//   * a record found in another space opens *there*, with the record open —
//     which is the whole reason the server sends a screen with every hit;
//   * a match nobody can see the reason for sorts under every match they can.
//
// The endpoint this drives, named so `scripts/affected.py` picks the file up
// when it changes — it attributes a Python change by the whitelisted dotted
// names in it:
//
//   oneapp.onespace.finding.look
//
// `docs/FRAPPE.md`, "What is missing", the first of the ten.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const FINDER = '[data-slot="finder"]'
const ROW = `${FINDER} [data-slot="row"]`

/**
 * Open it the way people do, and wait for it to be there.
 *
 * Two waits before the key, and each is a failure this had:
 *
 * The dock's own button is the one thing on the page that only exists once the
 * shell has mounted, and a `keydown` sent before that lands on a document with
 * no listener on it — four failures out of four.
 *
 * And then the screen itself, because the shell mounts before the router has
 * finished arriving: the app boots at `/`, which redirects, so for a moment
 * the dock is up and the route still says the standard space. The finder opens
 * on where you *are*, correctly, and where you are at that instant is not
 * where the test asked to go. Its list came back headed "Home · One".
 */
async function openFinder(page) {
  await page.locator('[data-slot="finder-open"]').waitFor({ timeout: 20_000 })
  await page.locator('[data-slot="list-search"] input').first()
    .waitFor({ timeout: 20_000 })
  await page.keyboard.press('Control+k')
  await page.locator(FINDER).waitFor({ timeout: 10_000 })
}

/** Type without submitting — the list follows the keystrokes, not Enter. */
async function type(page, text) {
  await page.locator(`${FINDER} input`).fill(text)
  // The box is debounced at 300ms and the fan-out is a query per screen.
  await expect.poll(
    async () => page.locator(ROW).count(),
    { timeout: 15_000 },
  ).toBeGreaterThan(0)
}

test.beforeEach(async ({ page, baseURL }, info) => {
  // A phone has neither of the two ways in: the dock is `hidden md:flex`, and
  // a touch keyboard has no Ctrl. That is a gap and not an oversight —
  // `docs/DESKTOP.md` stage 7 is the phone answer and it is the one stage of
  // that arc still pending — so it is named here rather than half-covered.
  test.skip(info.project.name === 'mobile', 'no dock and no Ctrl on a phone')
  await signIn(page, baseURL)
})

test('Ctrl+K opens it from anywhere, including out of a search box',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto('/one/space/onebook?screen=invoices')

    await openFinder(page)
    await expect(page.locator(FINDER)).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator(FINDER)).toBeHidden()

    // The list's own search box, which is where the house shortcuts stand
    // down: a bare letter must not act while somebody is typing, and a
    // modified one has to.
    const box = page.locator('[data-slot="list-search"] input').first()
    await box.waitFor({ timeout: 15_000 })
    await box.click()
    await openFinder(page)
    await expect(page.locator(FINDER)).toBeVisible()

    expectNoRealErrors(errors)
  })

test('it opens on the space you are standing in, before anything is typed',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto('/one/space/onebook?screen=invoices')
    await openFinder(page)

    const rows = page.locator(ROW)
    await expect(rows.first()).toBeVisible()
    // Every one of them, not merely the first: the failure this replaced was a
    // list of whichever two spaces sort first, with the one you are in absent.
    const many = await rows.count()
    expect(many).toBeGreaterThan(2)
    for (let at = 0; at < many; at += 1) {
      await expect(rows.nth(at)).toContainText('OneBook')
    }

    expectNoRealErrors(errors)
  })

test('a record found from one space opens in the space that has it',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto('/one/space/onebook?screen=invoices')
    await openFinder(page)
    await type(page, 'zzMeridian')

    // The fixture's client lives in RUA, and this search started in OneBook.
    const elsewhere = page.locator(ROW, { hasText: 'RUA' }).first()
    await elsewhere.waitFor({ timeout: 15_000 })
    await elsewhere.click()

    await expect(page).toHaveURL(/\/space\/rua\?/)
    // And it opens the record rather than merely the screen, which is what the
    // screen travelling with every hit is for.
    await expect(page).toHaveURL(/at=record%3A|at=record:/)

    expectNoRealErrors(errors)
  })

test('a hit whose own name explains it comes before one whose does not',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto('/one/space/onebook?screen=invoices')
    await openFinder(page)
    await type(page, 'zzMeridian')

    // A ledger entry matches this through the account it is against, and its
    // own name is a hash. It is a real answer and an unreadable one, so it
    // sorts under every row that says the word.
    const first = page.locator(ROW).first()
    await expect(first).toContainText('zzMeridian')

    expectNoRealErrors(errors)
  })
