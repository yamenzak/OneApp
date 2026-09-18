// The one surface in this product a stranger can reach.
//
// `docs/ONEFORMS.md`. Everything else in the suite signs in first, because
// everything else *is* the workspace; this spec is the first that deliberately
// does not — a public form is a page with no session, and the whole question
// is whether it works for somebody who has never had one.
//
// Four things, and each is a different half of the arc:
//
//   * a form can be made, and only over a doctype one of your spaces shows you
//     — the rule the module exists to keep;
//   * the builder puts fields on it and they come back;
//   * the page a stranger sees draws in this product's look and takes a
//     submission, which becomes an ordinary record;
//   * an invitation is a key, and a wrong one is refused.
//
// The endpoints this drives, named so `scripts/affected.py` picks the file up:
//
//   oneapp.oneforms.service.forms
//   oneapp.oneforms.service.make
//   oneapp.oneforms.service.layout
//   oneapp.oneforms.service.settings
//   oneapp.oneforms.public.page
//   oneapp.oneforms.public.send
//   oneapp.oneforms.invite.invite
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/** The form the fixture leaves behind — `scripts/seed_dev_space.py`. */
const ROUTE = 'zzapply-to-us'

test.beforeEach(async ({ page, baseURL }, info) => {
  // The builder is three columns of a desktop. The *public* form is not, and
  // the phone half of that is worth having — it is where a supplier opens a
  // link somebody mailed them — but it is a layout question nobody has
  // answered yet, and `docs/DESKTOP.md` stage 7 is where it belongs.
  test.skip(info.project.name === 'mobile', 'the builder is a desktop layout')
  await signIn(page, baseURL)
})

test('a form is made over a doctype one of your spaces shows you',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto('/one/forms')

    // The picker is the rule, drawn: it offers what `finding.placed` answers
    // and nothing else on the site. Found by what it says rather than by a
    // `data-slot`, because `Combobox` renders a trigger of its own and the
    // marker does not land where a child selector would look for it.
    await expect(page.getByPlaceholder('A form over…')).toBeVisible({
      timeout: 20_000,
    })
    // And nothing can be made until one is picked.
    await expect(page.locator('[data-slot="forms-new"]')).toBeDisabled()

    expectNoRealErrors(errors)
  })

test('the builder shows the doctype\'s own fields, and the form keeps them',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto(`/one/forms/${ROUTE}`)

    // What could go on: the doctype's fields, read off its meta.
    await page.locator('[data-slot="builder-spare"]').first()
      .waitFor({ timeout: 20_000 })

    // And what is on, which came back from the server rather than from the
    // browser's memory of putting it there.
    const rows = page.locator('[data-slot^="builder-row-"]')
    expect(await rows.count()).toBeGreaterThan(1)
    await expect(rows.first()).toContainText('Your name')

    // Save is off until something changes — a builder whose Save is always
    // live is a builder nobody trusts.
    await expect(page.locator('[data-slot="builder-save"]')).toBeDisabled()

    expectNoRealErrors(errors)
  })

test('a stranger can fill it in, and it lands as a record',
  async ({ browser, baseURL }) => {
    // A context of its own, with no cookies: this is the one test in the suite
    // whose whole point is that there is no session.
    const context = await browser.newContext()
    const page = await context.newPage()
    const errors = collectConsoleErrors(page)

    const key = await keyFor(page, baseURL)
    await page.goto(`/one/f/${ROUTE}?key=${key}`)

    const form = page.locator('[data-slot="public-form"]')
    await form.waitFor({ timeout: 20_000 })
    // Ours, not Frappe's portal: no navbar, no footer, no Bootstrap.
    await expect(page.locator('nav')).toHaveCount(0)

    // By label, not by `data-slot`: `FormControl` puts a fallthrough attribute
    // on the *control* rather than on a wrapper, so `[data-slot=…] input`
    // matches nothing. The label is also what the person filling it in reads.
    await page.getByLabel('Your name').fill('zzPlaywright Applicant')
    await page.getByLabel('Email').fill('zzplaywright@example.com')
    await page.locator('[data-slot="form-send"]').click()

    await expect(page.locator('[data-slot="form-sent"]')).toBeVisible({ timeout: 20_000 })

    expectNoRealErrors(errors)
    await context.close()
  })

test('a key that is not a key is refused, and says nothing about why',
  async ({ browser }) => {
    const context = await browser.newContext()
    const page = await context.newPage()

    await page.goto(`/one/f/${ROUTE}?key=definitely-not-a-key`)
    // The same sentence a missing form gets, and a taken-down one: out here
    // the difference between them is a fact about somebody's workspace.
    await expect(page.getByText('This form is not available')).toBeVisible({
      timeout: 20_000,
    })

    await context.close()
  })

/** A live invitation key, made through the service the workspace uses. */
async function keyFor(page, baseURL) {
  await signIn(page, baseURL)
  const response = await page.request.get(
    `${baseURL}/api/method/oneapp.oneforms.invite.invitations?name=${ROUTE}`,
  )
  const rows = (await response.json())?.message?.rows || []
  expect(rows.length, 'the fixture seeds one invitation').toBeGreaterThan(0)
  // And then thrown away: the page is opened without the cookie it just set,
  // because a key is supposed to be enough.
  await page.context().clearCookies()
  return rows[0].key
}
