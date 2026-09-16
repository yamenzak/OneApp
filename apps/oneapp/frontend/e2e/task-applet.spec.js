// OneTask: the applet, which is a door rather than a space.
//
// `docs/WORK.md` §12. Every row in this window is an ERPNext `Task` — the same
// one OneProject's board draws — and everything it does is something a person
// could have done by going there. What it is for is the cost of going there:
// catching a thought without leaving the page you were reading, ticking
// something off without losing your place.
//
// So the claims worth a browser are about *not moving*: the page underneath
// stays where it was, and what the window wrote is on the same rows the space
// reads back.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const WINDOW = '[data-window="onetask"]'

/** Whether this site carries ERPNext, whose Task is the only table here. */
async function hasErp(page, baseURL) {
  const response = await page.request.get(
    `${baseURL}/api/method/frappe.client.get_count?doctype=Project`,
  )
  return response.ok()
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
  test.skip(!(await hasErp(page, baseURL)), 'no ERPNext on this site')
})

test('a thought is caught without leaving the page it arrived on',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the dock is a desktop surface')
    const errors = collectConsoleErrors(page)
    const said = `zzRing the fabricator ${Date.now()}`

    // Somewhere that is not the tasks screen, because the whole claim is that
    // you do not have to go there.
    await page.goto('/one/space/oneproject?screen=projects&type=list')
    await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })

    await page.locator('[data-app="tasks"]').click()
    await expect(page.locator(WINDOW)).toBeVisible({ timeout: 25_000 })

    await page.locator('[data-slot="task-capture"]').fill(said)
    await Promise.all([
      page.waitForResponse((one) => one.url().includes('applet.capture')),
      page.locator('[data-slot="task-capture"]').press('Enter'),
    ])

    // It landed in the inbox, which is what "no project" means on ERPNext's
    // Task — one filter rather than a staging table somebody has to empty.
    await expect(page.locator(`${WINDOW} [data-slot="task-row"]`)
      .filter({ hasText: said })).toBeVisible({ timeout: 25_000 })
    await expect(page.locator(`${WINDOW} [data-slot="task-list-inbox"]`))
      .toBeVisible()

    // And the page never moved. A window that navigated the page under it
    // would be a screen with a narrower column, which is the thing this
    // replaced.
    await expect(page).toHaveURL(/screen=projects/)

    // A tick is the state, and a task in a Done column is off both lists.
    await Promise.all([
      page.waitForResponse((one) => one.url().includes('applet.tick')),
      page.locator(`${WINDOW} [data-slot="task-row"]`).filter({ hasText: said })
        .locator('[data-slot="task-tick"]').click(),
    ])
    await expect(page.locator(`${WINDOW} [data-slot="task-row"]`)
      .filter({ hasText: said })).toHaveCount(0, { timeout: 25_000 })

    // Put the fixture back. The row is an ordinary Task, so it goes the way
    // any row goes — from the space, which is the point.
    await page.goto('/one/space/oneproject?screen=tasks&type=list')
    const row = page.locator('[data-slot="list-row"]').filter({ hasText: said })
    await row.first().waitFor({ timeout: 25_000 })
    await row.first().locator('[data-slot="list-row-checkbox"]').click()
    await page.locator('[data-slot="selection-bar"]')
      .getByRole('button', { name: /^Delete/ })
      .click()
    await page.getByRole('dialog').getByRole('button', { name: 'Delete' }).click()
    await expect(row).toHaveCount(0, { timeout: 25_000 })

    expectNoRealErrors(errors)
  })

test('the window is the same rows the space reads back',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the dock is a desktop surface')
    const errors = collectConsoleErrors(page)

    await page.goto('/one/space/oneproject?screen=tasks&type=list')
    await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
    await page.locator('[data-app="tasks"]').click()
    await expect(page.locator(WINDOW)).toBeVisible({ timeout: 25_000 })

    // Mine is `_assign`, which is Frappe's own assignment and not a second
    // store — `docs/WORK.md` §2 — so what the handover rule put on somebody is
    // what this list shows.
    const mine = page.locator(`${WINDOW} [data-slot="task-row"]`)
    await expect(mine.filter({ hasText: 'zzRevised programme' }))
      .toBeVisible({ timeout: 25_000 })

    // And pressing one takes the *page* to it, in the space where records
    // live, leaving the window where it was.
    await mine.filter({ hasText: 'zzRevised programme' }).first().click()
    await expect(page).toHaveURL(/at=record%3A|at=record:/, { timeout: 25_000 })
    await expect(page.locator(WINDOW)).toBeVisible()

    expectNoRealErrors(errors)
  })
