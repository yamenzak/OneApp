// The notification panel, over the feed the framework was already writing.
//
// Nothing here produces a notification by hand. The test assigns a task the way
// a person would and then waits for the row to turn up, because the whole point
// of this feature is that Frappe's own producers already work and nothing
// rendered them. A fixture notification would prove the panel and not the wire.
//
// **This spec needs a worker.** `enqueue_create_notification` enqueues, so on a
// bench running only `dev.sh up` no notification is ever written and the panel
// is correctly empty. Run `scripts/dev.sh worker` beside it — see DEVLOOP.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

// Robin, because Frappe filters recipients by `User.email` and the
// Administrator's email is `admin@example.com` rather than `Administrator` —
// so assigning to the admin notifies nobody, on any Frappe site. Every
// ordinary user has name == email and works.
const COLLEAGUE = { user: 'robin@zzmock.test', password: 'Dev-Loop-2026!x' }
const TASK = 'zzmock-q3'

const bell = (page) => page.getByRole('button', { name: /Notifications/ })

test('an assignment turns up in the panel, and opens the record', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the bell is in the rail')
  const errors = collectConsoleErrors(page)

  // Assign, as a person would.
  await signIn(page, baseURL)
  await page.goto(`/one/space/zzmock?screen=tasks&record=${TASK}`)
  await page.locator('[data-slot="assign"]').waitFor({ timeout: 15_000 })

  // Start from nobody. The control is a *toggle*: on a record another spec
  // left assigned to Robin, the click below would take the assignment away
  // instead of making one, and then wait twenty seconds for a notification
  // that was never going to be written. Clearing first makes the precondition
  // a fact rather than a hope — this spec shares one fixture with every other.
  await clearAssignment(page)

  await page.locator('[data-slot="assign"]').click()
  await page.getByRole('option', { name: /robin/i }).click()
  await page.keyboard.press('Escape')

  // And the person assigned to sees it.
  await signIn(page, baseURL, COLLEAGUE)
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  await bell(page).click()
  // `.first()` because the panel is a feed rather than a fixture: an earlier
  // browser pass leaves its own notification behind — marking one read does not
  // delete it — so the newest is the one this run made.
  await expect(
    page.getByText(/assigned a new task/).first(),
    'no notification arrived. `scripts/dev.sh worker` has to be running: the ' +
      'framework enqueues these, so a bench with only a web server writes none.',
  ).toBeVisible({ timeout: 20_000 })

  // The framework writes the sentence with markup in it — the record's title
  // comes wrapped in a `<b>` — and a panel row is one line of text.
  await expect(page.getByText(/<b|<strong/)).toHaveCount(0)

  // Checked here rather than at the end: the click below opens the record as a
  // member, and a member cannot read the doctypes two of its Link fields point
  // at — so the pickers refuse and the console says so. That is a real wart and
  // it belongs to the record form, not to this.
  expectNoRealErrors(errors)

  // Clicking it opens the record, in the space and screen that shows that
  // doctype: a Notification Log names a doctype, and OneSpace has no doctype
  // routes, so the destination is resolved from the manifest.
  await page.getByText(/assigned a new task/).first().click()
  await expect(page).toHaveURL(new RegExp(`record=${TASK}`))
  await expect(
    page.locator('[data-slot="record-pane"]').getByText('File Q3 returns').first(),
  ).toBeVisible({ timeout: 15_000 })

  // Put the fixture back. Two reasons, and both have already cost a run: the
  // assignment control shows an assigned person as *selected*, so a second run
  // would click them off instead of on; and Frappe's assignment is a ToDo, on
  // a screen that lists ToDo, so every run leaves two rows in the fixture it
  // shares with every other spec.
  await signIn(page, baseURL)
  await page.goto(`/one/space/zzmock?screen=tasks&record=${TASK}`)
  await page.locator('[data-slot="assign"]').waitFor({ timeout: 15_000 })
  await page.locator('[data-slot="assign"]').click()
  await page.getByRole('option', { name: /robin/i }).click()
  await page.keyboard.press('Escape')
  await sweepAssignments(page)
})

/** Assign the fixture record to nobody, whatever it was on when we arrived. */
const clearAssignment = async (page) =>
  page.evaluate(
    async (task) =>
      fetch('/api/method/oneapp.oneapp_core.spaceview.assign', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Frappe-CSRF-Token': window.csrf_token || '',
        },
        body: JSON.stringify({
          space_code: 'zzmock',
          screen: 'tasks',
          name: task,
          users: [],
        }),
      }),
    TASK,
  )

/**
 * Delete the ToDos assignment leaves behind.
 *
 * Unassigning cancels them rather than deleting them, and this screen lists
 * ToDo — so without this the fixture grows by two rows every browser pass.
 * `assign.spec.js` does the same thing for the same reason.
 */
const sweepAssignments = async (page) =>
  page.evaluate(async () => {
    const ask = async (method, options) => {
      const res = await fetch(`/api/method/oneapp.oneapp_core.spaceview.${method}`, options)
      return (await res.json()).message
    }
    const first = await ask('rows?space_code=zzmock&screen=tasks&limit=500', {
      headers: { Accept: 'application/json' },
    })
    const doomed = (first?.rows || [])
      .filter((row) => String(row.description || '').includes('Assignment for'))
      .map((row) => row.name)
    if (!doomed.length) return 0
    await ask('remove', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': window.csrf_token || '',
      },
      body: JSON.stringify({ space_code: 'zzmock', screen: 'tasks', name: doomed }),
    })
    return doomed.length
  })

test('reading them empties the count', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the bell is in the rail')

  await signIn(page, baseURL, COLLEAGUE)
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  await bell(page).click()
  const clear = page.getByRole('button', { name: 'Mark all read' })
  // Only where there is something to mark: a control that does nothing is one
  // somebody presses once and stops trusting.
  if (await clear.count()) {
    await clear.click()
    await expect(clear).toHaveCount(0)
  }

  // The bell says so too — its accessible name is what carries the count for
  // anybody who cannot see the dot.
  await expect(page.getByRole('button', { name: 'Notifications' })).toBeVisible()
})

test('notification preferences are the framework\'s own, made legible', async ({
  page,
  baseURL,
}) => {
  await signIn(page, baseURL)
  await page.goto('/one/account')

  // Two switches and a list, which is the whole of Frappe's model: everything
  // off, email off, and per type whether email is wanted.
  const app = page.getByText('Notifications', { exact: true })
  await expect(app).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('Email me as well')).toBeVisible()

  // The per-type switches only exist while email is on — they are what email
  // is *for*, and a list of them under a switch that is off is a list that
  // does nothing.
  await expect(page.getByText('Assignment', { exact: true })).toBeVisible()
  await page.getByRole('switch').nth(1).click()
  await expect(page.getByText('Assignment', { exact: true })).toHaveCount(0)

  // And it is stored, not remembered: a reload says the same thing.
  await page.reload()
  await expect(page.getByText('Email me as well')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('Assignment', { exact: true })).toHaveCount(0)

  // Put it back.
  await page.getByRole('switch').nth(1).click()
  await expect(page.getByText('Assignment', { exact: true })).toBeVisible()
})
