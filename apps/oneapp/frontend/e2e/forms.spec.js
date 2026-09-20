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
//   * a page break is a step, and Send is only on the last one;
//   * a question only asked under a condition appears when it becomes true,
//     and what it collected is not sent when it does not;
//   * a file goes with the submission and lands as an attachment;
//   * a submission faster than a person could have read the page is refused;
//   * a form collects a document *and its lines*, and a step can be skipped by
//     an answer on an earlier one;
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
//   oneapp.oneforms.service.layout
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/** The form the fixture leaves behind — `scripts/seed_dev_space.py`. */
const ROUTE = 'zzapply-to-us'

/**
 * The second one, over `Opportunity`, which has a child table.
 *
 * `Job Applicant` has none, so nothing over it could show what stage 16 built.
 * Over `Task` because a stranger has to be able to *create* one, which rules
 * out most of what a space grants — the seeder says which two were tried
 * first. Open rather than keyed, so a stranger reaches it with no link.
 */
const ENQUIRY = 'zzask-us-for-something'

/**
 * Long enough to have read the page — `oneforms/guarding.LEAST` plus a margin.
 *
 * A wait rather than a workaround, and the test below it is the reason: a form
 * filled in faster than any person is a form a script filled in, and Playwright
 * is a script. Deliberately not `guarding.LEAST` read off the server: if that
 * number changes, this should fail and somebody should look.
 */
const READING = 3_500

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

/**
 * The builder is three columns of a desktop and stays one.
 *
 * The *public* form is not, and does not skip: it is the one page in this
 * product whose reader is as likely to be on a phone as not — a supplier
 * opening a link somebody mailed them — so §14 stage 15 unskipped it, and what
 * it found is in `docs/ONEFORMS.md`.
 */
const atADesk = (info) =>
  test.skip(info.project.name === 'mobile', 'the builder is a desktop layout')

test('a form is made over a doctype one of your spaces shows you',
  async ({ page }, info) => {
    atADesk(info)
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
  async ({ page }, info) => {
    atADesk(info)
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
    // Two steps, because the fixture's form has a page break in it — and Send
    // is not on the first one, which is the whole point of having them.
    await expect(page.locator('[data-slot="form-progress"]')).toBeVisible()
    await expect(page.locator('[data-slot="form-send"]')).toHaveCount(0)

    await page.getByLabel('Your name').fill('zzPlaywright Applicant')
    await page.getByLabel('Email').fill('zzplaywright@example.com')
    await page.locator('[data-slot="form-next"]').click()

    // And the second step is a different set of questions, reached without the
    // page reloading.
    await expect(page.getByLabel('Why you')).toBeVisible()

    await page.waitForTimeout(READING)
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
  async ({ page, browser, baseURL }, info) => {
    atADesk(info)
    // The whole round trip, because each half is checkable on its own and the
    // interesting claim is that they meet: what is typed in OneCode's editor
    // is what a stranger's browser runs.
    await page.goto(`/one/forms/${ROUTE}`)
    await page.locator('[data-slot="builder-style"]').click()

    const editor = page.locator('.cm-content')
    await editor.waitFor({ timeout: 20_000 })
    await editor.fill('[data-slot="form-title"] { color: rgb(220, 38, 38) }')
    await page.getByRole('button', { name: 'Save', exact: true }).last().click()

    // And while the builder is open: the corner says whose page this is.
    // `FormBuilder` is a second route, and a shell that matched one name fell
    // through to the workspace and said "OneSpace" on it.
    await expect(page.getByText('Forms', { exact: true }).first()).toBeVisible()

    const key = await freshKey(page, baseURL, 'zzstyle@example.com')
    const context = await browser.newContext()
    const seen = await context.newPage()
    await seen.goto(`/one/f/${ROUTE}?key=${key}`)

    const title = seen.locator('[data-slot="form-title"]')
    await title.waitFor({ timeout: 20_000 })
    await expect(title).toHaveCSS('color', 'rgb(220, 38, 38)')

    await context.close()
  })

test('a stylesheet that would fetch from another site is refused', async ({ page }, info) => {
  atADesk(info)
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

test('a step will not be left with a required question unanswered',
  async ({ browser, baseURL }) => {
    // The browser's own validation, which only works because one step at a
    // time is in the document — a `required` control on a step nobody can see
    // is a form that refuses to submit and will not say where.
    const context = await browser.newContext()
    const page = await context.newPage()

    const maker = await newSignedIn(browser, baseURL)
    await maker.goto(`/one/forms/${ROUTE}`)
    const key = await freshKey(maker, baseURL, 'zzsteps@example.com')
    await page.goto(`/one/f/${ROUTE}?key=${key}`)
    await page.locator('[data-slot="form-next"]').click()

    // Still on the first step, and the second step's questions are not here.
    await expect(page.getByLabel('Your name')).toBeVisible()
    await expect(page.getByLabel('Why you')).toHaveCount(0)

    await context.close()
  })

test('a question is asked only when its condition is true',
  async ({ page, browser, baseURL }, info) => {
    atADesk(info)
  // The fixture asks "Where you are" only once "What you are applying for" has
  // been answered. Drawn from a `{field, op, value}` tuple the server parsed —
  // nothing here evaluates anything, which is `oneforms/showing.py`'s whole
  // argument and the same one `client_script` lost on.
  await page.goto(`/one/forms/${ROUTE}`)
  const key = await freshKey(page, baseURL, 'zzbranch@example.com')

  const context = await browser.newContext()
  const seen = await context.newPage()
  await seen.goto(`/one/f/${ROUTE}?key=${key}`)

  await seen.getByLabel('Your name').fill('zzBranching Applicant')
  await seen.getByLabel('Email').fill('zzbranch@example.com')
  await seen.locator('[data-slot="form-next"]').click()

  await expect(seen.getByLabel('Where you are')).toHaveCount(0)
  await seen.getByLabel('What you are applying for').fill('Engineer')
  await expect(seen.getByLabel('Where you are')).toBeVisible()

  // And away again, because it is a condition rather than a reveal.
  await seen.getByLabel('What you are applying for').fill('')
  await expect(seen.getByLabel('Where you are')).toHaveCount(0)

  await context.close()
})

test('a file goes with the submission and lands on the record',
  async ({ page, browser, baseURL }, info) => {
    atADesk(info)
    // Inline in the POST, which is Frappe's own design: `accept` reads
    // `filename,data:…;base64,…` and writes the `File` itself. So there is no
    // upload endpoint on the public half, which is the point.
    await page.goto(`/one/forms/${ROUTE}`)
    const key = await freshKey(page, baseURL, 'zzcv@example.com')

    const context = await browser.newContext()
    const seen = await context.newPage()
    await seen.goto(`/one/f/${ROUTE}?key=${key}`)

    await seen.getByLabel('Your name').fill('zzCV Applicant')
    await seen.getByLabel('Email').fill('zzcv@example.com')
    await seen.locator('[data-slot="form-next"]').click()

    await seen.locator('[data-slot="field-resume_attachment"] input[type="file"]')
      .setInputFiles({
        name: 'zzcv.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('zzA short curriculum vitae.'),
      })
    await expect(seen.getByText('zzcv.txt')).toBeVisible()

    await seen.waitForTimeout(READING)
    await seen.locator('[data-slot="form-send"]').click()
    await expect(seen.locator('[data-slot="form-sent"]')).toBeVisible({ timeout: 20_000 })

    await context.close()
  })

test('a form filled in faster than a person can read it is refused',
  async ({ page, browser, baseURL }, info) => {
    atADesk(info)
    // The whole of the defence before this was a rate limit, which bounds how
    // fast rubbish arrives and says nothing about whether it is rubbish.
    // `oneforms/guarding.py` — a signed stamp handed out with the page, and a
    // form sent back inside three seconds was not read.
    await page.goto(`/one/forms/${ROUTE}`)
    const key = await freshKey(page, baseURL, 'zzfast@example.com')

    const context = await browser.newContext()
    const seen = await context.newPage()
    await seen.goto(`/one/f/${ROUTE}?key=${key}`)

    await seen.getByLabel('Your name').fill('zzToo Fast')
    await seen.getByLabel('Email').fill('zzfast@example.com')
    await seen.locator('[data-slot="form-next"]').click()
    await seen.locator('[data-slot="form-send"]').click()

    await expect(seen.getByText('That did not go through')).toBeVisible({
      timeout: 20_000,
    })
    await expect(seen.locator('[data-slot="form-sent"]')).toHaveCount(0)

    await context.close()
  })

test('a form collects a document and its lines', async ({ browser }) => {
  // `Table` was in `NEVER` from stage 1, so a form whose subject has parts —
  // an order, a claim, a schedule of rates — could not ask for them.
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto(`/one/f/${ENQUIRY}`)

  await page.getByLabel('What you need').first().fill('zzA new stockroom shelf')
  await page.locator('[data-slot="form-next"]').click()

  // One row, with the one column the *form* asked for — not both the child
  // doctype has. "Done" is not a stranger's to set.
  await page.locator('[data-slot="add-custom_steps"]').click()
  const row = page.locator('[data-slot="row-custom_steps-0"]')
  await expect(row.getByLabel('Step')).toBeVisible()
  await expect(row.getByLabel('Done')).toHaveCount(0)

  await row.getByLabel('Step').fill('zzMeasure the wall')

  // A second row added and taken out again, because a grid with an Add button
  // is a grid people add rows to by accident.
  await page.locator('[data-slot="add-custom_steps"]').click()
  await expect(page.locator('[data-slot="row-custom_steps-1"]')).toBeVisible()
  await page.locator('[data-slot="drop-custom_steps"]').last().click()
  await expect(page.locator('[data-slot="row-custom_steps-1"]')).toHaveCount(0)

  await page.locator('[data-slot="form-next"]').click()
  await page.waitForTimeout(READING)
  await page.locator('[data-slot="form-send"]').click()
  await expect(page.locator('[data-slot="form-sent"]')).toBeVisible({ timeout: 20_000 })

  await context.close()
})

test('a step nobody needs is not walked through', async ({ browser }) => {
  // The third step is asked only once the company site is answered. One field
  // watching another was stage 10; skipping a whole step is what makes a long
  // form short.
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto(`/one/f/${ENQUIRY}`)

  const steps = page.locator('[data-slot="form-progress"] > span')
  await expect(steps).toHaveCount(2)

  await page.getByLabel('What you need').first().fill('zzA new stockroom shelf')
  await expect(steps).toHaveCount(3)

  // And away again, because it is a condition rather than a reveal.
  await page.getByLabel('What you need').first().fill('')
  await expect(steps).toHaveCount(2)

  await context.close()
})

/** A signed-in page of its own, for a test that needs a second one. */
async function newSignedIn(browser, baseURL) {
  const page = await (await browser.newContext()).newPage()
  await signIn(page, baseURL)
  return page
}

/**
 * An invitation this test made, and then the cookies gone.
 *
 * Its own rather than the fixture's, because a key is spent by being opened:
 * the fixture seeds exactly one and "a stranger can fill it in" is the test it
 * belongs to. Made through the builder, which is how a person makes one, on a
 * page already sitting on that builder.
 *
 * Polled because `invite` mails as well as writes and the row lands a moment
 * after the press.
 */
async function freshKey(page, baseURL, address) {
  await page.getByPlaceholder('Their address').fill(address)
  await page.locator('[data-slot="builder-invite"]').click()

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
