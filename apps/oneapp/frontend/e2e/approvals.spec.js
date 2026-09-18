// The approvals inbox, which is the one screen that acts on somebody else's
// records from outside their space.
//
// Every other screen in this product is a space's own: it resolves through a
// manifest, it lists one doctype, and what it may do is what that space
// granted. This is a list of *other people's* screens, assembled from
// `Workflow Action` rows the framework wrote, and pressing a verb on it reaches
// through to `spaceview/docstate.workflow_action` in a space the reader is not
// standing in. Three things could go wrong there and none of them would be
// visible from any other spec.
//
// The fixture is the dev seed's own workflow — `zzApproval` under `zzWorkflow`,
// three records in `zzDraft`, in the `zzmock` space. `scripts/seed_dev_space.py`
// `_seed_approvals` makes it, and it exists because core Frappe has exactly one
// submittable doctype and it is a sync job.
//
// The endpoints this drives, named so `scripts/affected.py` picks the file up —
// it attributes a Python change by the whitelisted dotted names in it:
//
//   oneapp.onespace.waiting.mine
//   oneapp.onespace.waiting.how_many
//   oneapp.onespace.spaceview.workflow_action
//
// `docs/FRAPPE.md`, "What is missing", the third of the ten.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const WAITING = '/one/space/one?screen=waiting'
const ROW = '[data-slot^="waiting-zz"]'

/** Whether this site carries the seed's workflow fixture. */
async function hasWorkflow(page, baseURL) {
  const response = await page.request.get(
    `${baseURL}/api/method/frappe.client.get_count?doctype=Workflow Action`,
  )
  return response.ok()
}

test.beforeEach(async ({ page, baseURL }, info) => {
  // The screen is reachable on a phone — it is a rail entry like any other —
  // but the rows put the title, the state and two verbs on one line, and at
  // 390px that is a layout question nobody has answered yet.
  test.skip(info.project.name === 'mobile', 'the row is a desktop line for now')
  await signIn(page, baseURL)
  test.skip(!(await hasWorkflow(page, baseURL)), 'no workflow on this site')
})

test('it lists what is waiting, from a space you are not standing in',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto(WAITING)

    const rows = page.locator(ROW)
    await rows.first().waitFor({ timeout: 20_000 })
    expect(await rows.count()).toBeGreaterThan(0)

    // Where it is, which is the whole reason the server places a row: this
    // screen is in One and every one of these records lives somewhere else.
    await expect(rows.first()).toContainText('MockSpace')

    expectNoRealErrors(errors)
  })

test('the title opens the record on the screen that shows it',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto(WAITING)
    await page.locator(ROW).first().waitFor({ timeout: 20_000 })

    await page.locator('[data-slot="waiting-open"]').first().click()
    await expect(page).toHaveURL(/\/space\/zzmock\?/)
    await expect(page).toHaveURL(/at=record%3A|at=record:/)

    expectNoRealErrors(errors)
  })

test('a verb moves the document and the list says so', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto(WAITING)

  const first = page.locator(ROW).first()
  await first.waitFor({ timeout: 20_000 })
  const before = await first.innerText()

  await first.locator('[data-slot="waiting-act"]').first().click()

  // Re-read rather than removed: a transition can hand the document straight
  // back to the same person, which is what the seed's own workflow does —
  // zzDraft sends to zzPending and this reader approves that too. So the
  // assertion is that the row *changed*, not that it went.
  await expect
    .poll(async () => first.innerText(), { timeout: 20_000 })
    .not.toBe(before)

  expectNoRealErrors(errors)
})
