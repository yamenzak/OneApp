// The list you came from, in a window, while you read one of its rows.
//
// `docs/DESKTOP.md` stage 3. The pane is going and a record is becoming a page,
// and the thing the pane was actually for — mark this one done, glance at the
// next, come back — has to survive that. The breadcrumb is where it went.
//
// What is worth a browser here is the one claim the design rests on: the window
// holds *the* list and not a copy of it. A copy built from the saved view would
// look identical on a screen nobody had narrowed, and would quietly lose the
// search, the unsaved filter and the scroll — which is exactly the state
// somebody working through a list has. So the search box is what this asserts.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

// OneHR's People, because its manifest declares a showcase — a record there
// is a place rather than a form, so it takes the page, which is the case this
// whole stage is about.
const PEOPLE = '/one/space/onehr?screen=people&type=list'

const rows = (where) => where.locator('[data-slot="list-row"]')

async function openPeople(page) {
  await page.goto(PEOPLE)
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no HRMS, so the space is not seeded')
  await rows(page).first().waitFor({ timeout: 25_000 })
}

test('the trail names the list you came from, and pressing it opens the list',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'a phone has one surface and no desk')
    const errors = collectConsoleErrors(page)

    await openPeople(page)
    const first = await rows(page).first().innerText()
    await rows(page).first().click()

    // A record used to replace the trail — `🏠 / Ahmad` — so the list was gone
    // from the page and from the address. It is named again, as a control.
    const crumb = page.locator('[data-slot="crumb-peek"]')
    await expect(crumb).toBeVisible({ timeout: 20_000 })
    await expect(crumb).toContainText('People')

    const window_ = page.locator('[data-window="pip"]')
    await expect(window_).toBeHidden()

    await crumb.click()
    await expect(window_).toBeVisible()
    // And what is in it is a list of rows, not an empty frame with a name on
    // it — which is what a teleport whose target never resolved looks like.
    await expect(rows(window_).first()).toBeVisible()
    expect(await rows(window_).count()).toBeGreaterThan(1)

    // The page underneath is still the record. The whole point of a window is
    // that it did not take you anywhere.
    await expect(page.locator('[data-slot="object-pane"]')).toBeVisible()
    expect(first.length).toBeGreaterThan(0)

    expectNoRealErrors(errors)
  })

test('picking a row in the window moves the page under it, and the window stays',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'a phone has one surface and no desk')

    await openPeople(page)
    await rows(page).first().click()
    await page.locator('[data-slot="crumb-peek"]').click()

    const window_ = page.locator('[data-window="pip"]')
    await expect(rows(window_).first()).toBeVisible({ timeout: 20_000 })

    const subject = page.locator('[data-slot="breadcrumb"] [data-slot="record-chip"]')
    const was = await subject.innerText()

    // The second row, which is a different person from the one open.
    await rows(window_).nth(1).click()

    await expect(subject).not.toHaveText(was, { timeout: 20_000 })
    // Still there, still holding the list. This is the checkpoint the whole
    // stage is written to: pick the next one without losing where you were.
    await expect(window_).toBeVisible()
    await expect(rows(window_).first()).toBeVisible()
  })

test('the window holds the list itself, so a search survives being put in it',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'a phone has one surface and no desk')

    await openPeople(page)

    // Narrow it to one name. A copy of this list built from the screen's saved
    // view would come back unnarrowed, because nobody saved this.
    const box = page.getByPlaceholder('Search').first()
    await box.fill('zzNoor')
    await expect(rows(page)).toHaveCount(1, { timeout: 20_000 })

    await rows(page).first().click()
    await page.locator('[data-slot="crumb-peek"]').click()

    const window_ = page.locator('[data-window="pip"]')
    await expect(window_).toBeVisible({ timeout: 20_000 })
    // One row, and the box still holding what was typed into it: the same
    // component, moved, rather than a second one built from a declaration.
    await expect(rows(window_)).toHaveCount(1)
    await expect(window_.getByPlaceholder('Search').first()).toHaveValue('zzNoor')
  })

test('closing the window puts the list back where it was', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a phone has one surface and no desk')

  await openPeople(page)
  await rows(page).first().click()
  await page.locator('[data-slot="crumb-peek"]').click()

  const window_ = page.locator('[data-window="pip"]')
  await expect(rows(window_).first()).toBeVisible({ timeout: 20_000 })

  await window_.locator('[data-slot="window-close"]').click()
  await expect(window_).toBeHidden()

  // And not into the page, which still belongs to the record: the list goes
  // back to being the covered thing it was, so closing the record comes back
  // to the same rows rather than to a screen that fetches itself again.
  //
  // Hidden and not absent, which is the whole mechanism: `v-show` sets
  // `display: none` and leaves the rows in the DOM, and it has to — a `v-if`
  // here would throw the list away and rebuild it, which is what the pane
  // spent its whole life avoiding.
  await expect(page.locator('[data-slot="object-pane"]')).toBeVisible()
  await expect(rows(page).first()).toBeHidden()
  expect(await rows(page).count()).toBeGreaterThan(0)
})

test('leaving the screen takes the window with it', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a phone has one surface and no desk')

  await openPeople(page)
  await rows(page).first().click()
  await page.locator('[data-slot="crumb-peek"]').click()

  const window_ = page.locator('[data-window="pip"]')
  await expect(rows(window_).first()).toBeVisible({ timeout: 20_000 })

  // A window whose teleport target has gone is an empty frame with a name on
  // it and no way to tell it is empty on purpose.
  await page.goto('/one/files')
  await expect(window_).toBeHidden({ timeout: 20_000 })
})
