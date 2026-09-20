// What a record page is made of, now that a record is a page.
//
// `docs/DESKTOP.md` stage 5. Three things moved out of places that were wrong
// for them — the doctype's field groups out of a strip inside Details, the
// pipeline out of a badge in the trail, Meta out of a tab — and the rule that
// decides where each went is that it costs height or a press, never width. A
// column down the side was built first and deleted: five hundred pixels of
// chrome on a 1280 window is the pane's arithmetic in a different coat.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

/** Compliance: a doctype with one field group, which is the no-band case. */
const openCompliance = async (page) => {
  await page.goto('/one/space/zzmock?screen=compliance')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="object-pane"]').waitFor({ timeout: 20_000 })
}

/** An applicant: OneHR declares hiring verbs on that screen, which is the
 *  case the band has to hold beside the pipeline. */
const openApplicant = async (page) => {
  await page.goto('/one/space/onehr?screen=applicants&type=list')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no HRMS, so the space is not seeded')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="object-pane"]').waitFor({ timeout: 20_000 })
}

/** An invoice: submittable, so it has the framework's own three-state pipeline
 *  and several field groups. */
const openInvoice = async (page) => {
  await page.goto('/one/space/rua?screen=invoices')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="object-pane"]').waitFor({ timeout: 20_000 })
}

test('the pipeline is a band, and the state it is at is the lit one',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the rail and the band are a desktop page')
    const errors = collectConsoleErrors(page)
    await openInvoice(page)

    // Every state, in order, rather than the one it happens to be at: "Approved"
    // says where you are and nothing about how far along that is.
    const band = page.locator('[data-slot="record-band"]')
    await expect(band).toBeVisible({ timeout: 20_000 })
    await expect(band).toContainText('Draft')
    await expect(band).toContainText('Submitted')
    await expect(band).toContainText('Cancelled')

    // Exactly one is `now`, and it is the one the record is in. The server
    // works `standing` out from the index rather than from the words.
    const now = band.locator('[data-standing="now"]')
    await expect(now).toHaveCount(1)

    // And it is a band: it costs height and takes nothing off the form's width.
    const inset = await page.locator('[data-slot="shell-inset"]').boundingBox()
    const box = await band.boundingBox()
    expect(Math.round(box.width)).toBe(Math.round(inset.width))
    expect(box.height).toBeLessThan(64)

    expectNoRealErrors(errors)
  })

test('a doctype with nothing to do and nowhere to go draws no band',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the rail and the band are a desktop page')
    await openCompliance(page)

    // Conditional is the whole reason this is affordable. A Compliance Document
    // neither submits, nor runs on a workflow, nor has a verb its screen
    // declares — so there is nothing for a band to hold, and a row drawn to say
    // nothing is a row.
    await expect(page.locator('[data-slot="record-band"]')).toHaveCount(0)
  })

test('the screen\'s own verbs are in the band, not beside Delete',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the band is a desktop page')
    await openApplicant(page)

    // They were in the header, three feet from the state they advance and
    // beside the two things that end the record. What is left up there is the
    // menu holding those: Cancel unwinds it, Delete destroys it, and neither
    // belongs next to a green button.
    const band = page.locator('[data-slot="record-band"]')
    await expect(band.locator('[data-slot="screen-actions"]')).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('[data-slot="record-controls"] [data-slot="screen-actions"]'))
      .toHaveCount(0)
  })

test('a change says what it is before you save it', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'typing into a phone form is its own pass')
  const errors = collectConsoleErrors(page)
  await openCompliance(page)

  const bar = page.locator('[data-slot="record-unsaved"]')
  await expect(bar).toHaveCount(0)

  const box = page.getByLabel('Document Number')
  await box.fill('CN-TEST-0001')
  await expect(bar).toBeVisible()
  await expect(bar).toContainText('1 change not saved')
  // Folded, it names the field. A Save button says only that *something*
  // changed, which on a forty-field record is a question rather than an answer.
  await expect(bar).toContainText('Document Number')

  // Opened, it says what it was and what it is about to be.
  await bar.locator('[data-slot="unsaved-toggle"]').click()
  await expect(bar.locator('[data-slot="unsaved-diff"]')).toContainText('CN-TEST-0001')

  // And Save is here and nowhere else: two buttons doing one thing is a reader
  // deciding which is the real one.
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toHaveCount(1)

  // Discard is the other half of showing a diff — a change you can see is one
  // you can decide against.
  await bar.locator('[data-slot="unsaved-discard"]').click()
  await expect(bar).toHaveCount(0)
  await expect(box).not.toHaveValue('CN-TEST-0001')

  expectNoRealErrors(errors)
})

test('what the record is, is a popover off its name — not a tab',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'a phone keeps the tab; it has no line with room')
    const errors = collectConsoleErrors(page)
    await openCompliance(page)

    // It was never a place you went: it is a paragraph about the thing you are
    // looking at, so it hangs off the line that names it.
    await expect(page.getByRole('tab', { name: 'Meta' })).toHaveCount(0)

    await page.locator('[data-slot="record-about"]').click()
    const about = page.getByText('Assigned to', { exact: true })
    await expect(about).toBeVisible({ timeout: 15_000 })

    expectNoRealErrors(errors)
  })

test("the doctype's own groups are places in the rail, not a strip inside one",
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'a phone has no rail to put them in')
    const errors = collectConsoleErrors(page)
    await openInvoice(page)

    const rail = page.locator('[data-slot="record-tabs-rail"]')
    await expect(rail).toBeVisible({ timeout: 20_000 })

    // Two kinds of thing, said apart. A field group on this record and a screen
    // listing other records are not the same, and fifteen entries in one
    // undifferentiated column is where you have to read both to tell which.
    await expect(rail).toContainText('This record')
    await expect(rail).toContainText('Related')

    // And the strip that was inside Details is gone: its groups are triggers in
    // the rail now, so the form draws one group and no strip of its own.
    const groups = rail.getByRole('tab')
    expect(await groups.count()).toBeGreaterThan(4)

    expectNoRealErrors(errors)
  })

test('the form asks its own box how many columns it has, not the window',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'one column there, and always was')
    await openInvoice(page)

    // `md:grid-cols-3` was a question about the viewport, which was right for
    // as long as a form had the page to itself. The witness is not the count —
    // that changes with the doctype — it is that nothing overflows: a grid
    // wider than its box is labels running past the panel, which is what three
    // columns of 243px did to "Is Rate Adjustment Entry (Debit Note)".
    const over = await page.evaluate(() =>
      [...document.querySelectorAll('.oneapp-form-grid')]
        .map((el) => el.scrollWidth - el.clientWidth)
        .filter((one) => one > 1),
    )
    expect(over, 'a form column is wider than the box it is in').toEqual([])
  })
