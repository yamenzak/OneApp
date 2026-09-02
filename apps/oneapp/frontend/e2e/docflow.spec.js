// Where a document stands, and what may be done to it next.
//
// Two mechanisms and one row of buttons. The fixture's `zzApproval` is
// submittable *and* carries a workflow, so what this proves is the rule the
// whole thing turns on: a workflow owns the transition, so the header says
// "zzSend" rather than "Submit" — and approving is what submits.
//
// Each test makes its own record and deletes it. There is no resetting a
// shared one: `zzVoided` carries docstatus 2, and a cancelled document has no
// transitions out of it by design — which is the fixture being honest about
// what a workflow is rather than a gap in it.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const SCREEN = 'approvals'

const call = (page, method, body) =>
  page.evaluate(
    ([name, payload]) =>
      fetch(`/api/method/oneapp.oneapp_core.spaceview.${name}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Frappe-CSRF-Token': window.csrf_token || '',
        },
        body: JSON.stringify({ space_code: 'zzmock', screen: 'approvals', ...payload }),
      })
        .then((r) => r.json())
        .then((found) => found.message),
    [method, body],
  )

/**
 * Take it back off the site.
 *
 * A submitted document cannot be deleted, so anything that reached an approved
 * state is voided first — which is the same walk a person would have to do,
 * and the reason the fixture has a voiding transition at all.
 */
const clean = async (page, name) => {
  const found = await page.evaluate(([record]) => {
    const asked = new URLSearchParams({
      space_code: 'zzmock',
      screen: 'approvals',
      name: record,
    })
    return fetch(`/api/method/oneapp.oneapp_core.spaceview.record?${asked}`)
      .then((r) => r.json())
      .then((one) => one.message?._state?.docstatus)
  }, [name])
  if (found === 1) await call(page, 'workflow_action', { name, action: 'zzVoid' })
  await call(page, 'remove', { name })
}

/** A record of this run's own, opened in the pane. */
const make = async (page, baseURL, title) => {
  await signIn(page, baseURL)
  await page.goto(`/one/space/zzmock?screen=${SCREEN}`)
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  const made = await call(page, 'save', { values: { title, amount: 42 } })
  await page.goto(`/one/space/zzmock?screen=${SCREEN}&record=${made.name}`)
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 15_000 })
  return made.name
}

const state = (page) => page.locator('[data-slot="doc-state"]')
const step = (page, action) =>
  page.locator('[data-slot="doc-action-workflow"]').filter({ hasText: action })

test('a workflow owns the transition, and approving is what submits', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the record header collapses on a phone')
  const errors = collectConsoleErrors(page)

  const name = await make(page, baseURL, `zzflow one ${Date.now()}`)

  // The workflow's own state, not the framework's word for the docstatus —
  // and said once. The screen names no `status_field`, because a workflow's
  // state *is* where the record stands and the header is where it is said.
  await expect(state(page)).toHaveText('zzDraft')
  await expect(page.locator('[data-slot="record-status"]')).toHaveCount(0)

  // And its own action — which is the rule: no Submit button beside it.
  await expect(page.getByRole('button', { name: 'Submit', exact: true })).toHaveCount(0)
  await step(page, 'zzSend').click()
  await expect(state(page)).toHaveText('zzPending', { timeout: 15_000 })

  // Approving takes the record to a state whose doc_status is 1, so the
  // framework submits it — which is the whole reason the plain button is gone.
  await step(page, 'zzApprove').click()
  await expect(state(page)).toHaveText('zzApproved', { timeout: 15_000 })

  // And the framework agrees: the record is submitted, which nothing in the
  // header ever said in so many words.
  const docstatus = await page.evaluate(([record]) => {
    const asked = new URLSearchParams({
      space_code: 'zzmock',
      screen: 'approvals',
      name: record,
    })
    return fetch(`/api/method/oneapp.oneapp_core.spaceview.record?${asked}`)
      .then((r) => r.json())
      .then((one) => one.message?._state?.docstatus)
  }, [name])
  expect(docstatus).toBe(1)

  await clean(page, name)
  expectNoRealErrors(errors)
})

test('the step that cancels asks before it runs', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the record header collapses on a phone')
  const errors = collectConsoleErrors(page)

  const name = await make(page, baseURL, `zzflow two ${Date.now()}`)
  await call(page, 'workflow_action', { name, action: 'zzSend' })
  await call(page, 'workflow_action', { name, action: 'zzApprove' })
  await page.reload()
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 15_000 })
  await expect(state(page)).toHaveText('zzApproved')

  // The voiding step is not a button. `cancels` comes off the next state's own
  // doc_status rather than off the word on the button — "zzVoid" says nothing
  // about a ledger, and the state it leads to says everything — and everything
  // that cancels lives behind the three dots rather than beside the step the
  // record is actually waiting for.
  await expect(step(page, 'zzVoid')).toHaveCount(0)
  await page.locator('[data-slot="record-more"]').click()
  await page.getByRole('menuitem', { name: 'zzVoid' }).click()
  await expect(page.getByText(/cancels it/)).toBeVisible()
  await page.getByRole('button', { name: 'Never mind' }).click()
  await expect(state(page)).toHaveText('zzApproved')

  await clean(page, name)
  expectNoRealErrors(errors)
})
