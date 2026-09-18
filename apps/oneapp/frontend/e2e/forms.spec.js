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
//   * an invitation is a key, and a wrong one is refused;
//   * and the stylesheet somebody writes in OneCode reaches the page a
//     stranger loads, which is the one place in this product where something
//     a customer typed runs in a browser that is not theirs.
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
//   oneapp.oneforms.service.style
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

test('a stylesheet written in the builder is worn by the public page',
  async ({ page, browser, baseURL }) => {
    // The whole round trip, because each half is checkable on its own and the
    // interesting claim is that they meet: what is typed in OneCode's editor
    // is what a stranger's browser runs.
    await page.goto(`/one/forms/${ROUTE}`)
    await page.locator('[data-slot="builder-style"]').click()

    const editor = page.locator('.cm-content')
    await editor.waitFor({ timeout: 20_000 })
    await editor.fill('[data-slot="form-title"] { color: rgb(220, 38, 38) }')
    await page.getByRole('button', { name: 'Save', exact: true }).last().click()

    // Its own invitation rather than the fixture's. A key is used up by being
    // opened, and the test above is the one the fixture's belongs to.
    await page.getByPlaceholder('Their address').fill('zzstyle@example.com')
    await page.locator('[data-slot="builder-invite"]').click()
    const key = await unusedKey(page, baseURL)

    const context = await browser.newContext()
    const seen = await context.newPage()
    await seen.goto(`/one/f/${ROUTE}?key=${key}`)

    const title = seen.locator('[data-slot="form-title"]')
    await title.waitFor({ timeout: 20_000 })
    await expect(title).toHaveCSS('color', 'rgb(220, 38, 38)')

    await context.close()
  })

test('a stylesheet that would fetch from another site is refused', async ({ page }) => {
  // The rule, said where somebody writing one would meet it. A CSS rule naming
  // an external URL is a beacon on a page strangers were asked to open,
  // whether or not anybody meant it as one.
  await page.goto(`/one/forms/${ROUTE}`)
  await page.locator('[data-slot="builder-style"]').click()

  const editor = page.locator('.cm-content')
  await editor.waitFor({ timeout: 20_000 })
  await editor.fill('@import url(https://example.com/theme.css);')
  await page.getByRole('button', { name: 'Save', exact: true }).last().click()

  await expect(page.getByText('cannot fetch anything').first()).toBeVisible({
    timeout: 20_000,
  })
})

/**
 * An invitation nobody has opened yet, and then the cookies gone.
 *
 * Polled because `invite` mails as well as writes and the row lands a moment
 * after the press. Unused, because a key is spent by being opened — the
 * fixture seeds exactly one, and the test above is the one it belongs to.
 */
async function unusedKey(page, baseURL) {
  let spare = []
  await expect.poll(async () => {
    const response = await page.request.get(
      `${baseURL}/api/method/oneapp.oneforms.invite.invitations?name=${ROUTE}`,
    )
    spare = ((await response.json())?.message?.rows || [])
      .filter((one) => !one.first_used_on)
    return spare.length
  }, { timeout: 20_000 }).toBeGreaterThan(0)

  // And then thrown away, like `keyFor`: the page is opened without the cookie
  // that read them, because a key is supposed to be enough.
  await page.context().clearCookies()
  return spare[spare.length - 1].key
}

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
