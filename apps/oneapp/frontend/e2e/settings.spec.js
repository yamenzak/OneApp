// The settings dialog, for the two people who open it.
//
// It used to be an admin's dialog: every tab in it was the workspace's, so it
// was offered where `session.isAdmin` and nowhere else, and a member had no way
// to change their own name. The tabs are declared server-side with an audience
// each now, so this is one dialog and what is in it depends on who opened it.
//
// The audiences themselves are `tests/test_settings_tabs.py`, where they can be
// asked directly. What a browser can prove is the half that was wrong: the door
// is offered, it opens, and it opens onto different things.
import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const MEMBER = { user: 'robin@zzmock.test' }

// `signIn` posts to an absolute URL, and the helper below is called from tests
// that have no `baseURL` fixture in scope.
const BASE = 'http://space.localhost:8001'

const dialog = (page) => page.getByRole('dialog')

// By slot rather than by label: a tab's name is also its panel's heading, so
// `getByText('Profile')` is two elements the moment the tab is the open one.
const tab = (page, key) => page.locator(`[data-slot="settings-tab-${key}"]`)
const heading = (page, label) => dialog(page).getByText(label, { exact: true })

/**
 * Press something and wait for the write to land.
 *
 * Not "wait for Save to be disabled": it is disabled *while* saving too, so
 * that assertion passes the instant the click happens and the read below then
 * races the request. The response is the only honest signal.
 */
async function saved(page, press) {
  await Promise.all([
    page.waitForResponse((res) => res.url().includes('me.save_profile')),
    press(),
  ])
}

async function openSettings(page, who) {
  await signIn(page, BASE, who)
  await page.goto('/one/files')
  await page.locator('[data-slot="settings-link"]').click()
  await expect(dialog(page)).toBeVisible()
  // The tabs are the server's list, so the dialog is visible for a moment with
  // nothing in the strip. Profile is the one tab everybody has, which makes it
  // the honest signal that the list has arrived.
  await expect(tab(page, 'profile')).toBeVisible()
}

test('the gear is in the rail for everybody, not only an admin',
  async ({ page, baseURL }, info) => {
    await signIn(page, baseURL, MEMBER)
    await page.goto('/one/files')
    // Both shells, from the one declaration in `lib/shell/nav.js`: the rail's
    // footer on a desktop, and a row in the More sheet on a phone, which draws
    // no rail. Same slot on both, which is the point.
    if (info.project.name === 'mobile') {
      await page.getByRole('button', { name: 'More' }).click()
    }
    // Generously: the rail is drawn from the session's spaces, so on a cold
    // start this is waiting for a fetch rather than for a render.
    await expect(page.locator('[data-slot="settings-link"]'))
      .toBeVisible({ timeout: 15_000 })
  })

test('a member sees their own settings and none of the workspace it',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone draws no rail')
    const errors = collectConsoleErrors(page)
    await openSettings(page, MEMBER)

    for (const key of ['profile', 'security', 'notifications', 'appearance']) {
      await expect(tab(page, key)).toBeVisible()
    }

    // Not one workspace tab, and no heading over an empty column either: a
    // section is built from the tabs rather than from a list of names.
    await expect(heading(page, 'Workspace')).toHaveCount(0)
    for (const key of ['branding', 'signin', 'naming', 'ai']) {
      await expect(tab(page, key)).toHaveCount(0)
    }

    expectNoRealErrors(errors)
  })

test('an admin sees the workspace as well as themselves', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no rail')
  await openSettings(page)

  await expect(heading(page, 'You')).toBeVisible()
  await expect(heading(page, 'Workspace')).toBeVisible()
  await expect(tab(page, 'profile')).toBeVisible()
  await expect(tab(page, 'branding')).toBeVisible()
})

test('a member opens on a tab they have, not the one last asked for',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone draws no rail')
    // The dialog remembers its tab across sessions in one browser, so a member
    // signing in after an admin would otherwise open on a blank panel.
    await openSettings(page, MEMBER)
    await expect(dialog(page)).toContainText('Your name and how you are reached.')
  })

test('a member can change their own name', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no rail')
  await openSettings(page, MEMBER)

  // FormControl forwards fallthrough attributes to the control itself, so the
  // slot is the input rather than a wrapper around one.
  const first = page.locator('input[data-slot="profile-first_name"]')
  const said = `Robin ${Date.now()}`
  await first.fill(said)
  await saved(page, () => page.locator('[data-slot="profile-save"]').click())

  // Read back from the server rather than from the field that was typed in.
  const res = await page.request.get('/api/method/oneapp.oneapp_core.me.profile')
  const fields = (await res.json()).message.fields
  expect(fields.find((one) => one.key === 'first_name').value).toBe(said)

  // Put it back, so the fixture is what the next spec expects.
  await first.fill('Robin')
  await saved(page, () => page.locator('[data-slot="profile-save"]').click())
})

test("a member cannot write the workspace's settings by asking directly",
  async ({ page, baseURL }) => {
    await signIn(page, baseURL, MEMBER)
    // The tabs decide what is *shown*; this is the door itself, which never
    // moved — `workspace.save` has always checked the group's own roles.
    const refused = await page.request.post(
      '/api/method/oneapp.oneapp_core.workspace.save',
      { data: { group: 'branding', values: JSON.stringify({ workspace_name: 'Mine' }) } },
    )
    expect(refused.ok()).toBe(false)
  })

test('a profile write is refused for anything outside the allowlist',
  async ({ page, baseURL }) => {
    await signIn(page, baseURL, MEMBER)
    // `User` is a large doctype and most of it is administration, so the
    // endpoint takes a fixed set of fields rather than a fieldname.
    const refused = await page.request.post(
      '/api/method/oneapp.oneapp_core.me.save_profile',
      { data: { values: JSON.stringify({ enabled: 1, role_profile_name: 'System Manager' }) } },
    )
    expect(refused.ok()).toBe(false)
  })

test('every tab an admin is offered actually draws something', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no rail')
  const errors = collectConsoleErrors(page)
  await openSettings(page)

  // The contract `tabs.py` and `SettingsShell.vue` share, checked end to end
  // rather than by reading both files: a key with no component renders as an
  // empty panel, and Vue says nothing about it.
  const keys = await page.locator('[data-slot^="settings-tab-"]').evaluateAll(
    (all) => all.map((one) => one.dataset.slot.replace('settings-tab-', '')),
  )
  expect(keys.length).toBeGreaterThan(12)

  for (const key of keys) {
    await page.locator(`[data-slot="settings-tab-${key}"]`).click()
    const panel = page.locator(`[role="tabpanel"][data-state="active"]`)
    // Something with words in it. An empty panel is what a missing component
    // looks like, and it is the failure this whole registry exists to make
    // impossible.
    await expect(panel).not.toBeEmpty()
    await expect(panel).toContainText(/\w{3}/, { timeout: 15_000 })
  }

  expectNoRealErrors(errors)
})

test('the workspace decides who may connect an outside mailbox',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone draws no rail')
    await openSettings(page)
    await tab(page, 'mail').click()

    // Three states, and the middle one asks which domains. A connected mailbox
    // brings somebody's own mail into a workspace their colleagues hold
    // addresses in, so it is the workspace's answer and not only the person's.
    const only = page.locator('[data-slot="mail-policy-domains"]')
    await expect(only).toBeVisible({ timeout: 15_000 })

    await Promise.all([
      page.waitForResponse((res) => res.url().includes('set_connect_policy')),
      only.click(),
    ])
    await expect(dialog(page).getByText('Allowed domains')).toBeVisible()

    // Put it back: anybody, which is what most workspaces want.
    await Promise.all([
      page.waitForResponse((res) => res.url().includes('set_connect_policy')),
      page.locator('[data-slot="mail-policy-any"]').click(),
    ])
    await expect(dialog(page).getByText('Allowed domains')).toHaveCount(0)
  })

// A field that hangs off another one's *value*, not its truthiness. Frappe's
// own doctype states this rule — `depends_on: eval:doc.pdf_page_size ==
// "Custom"` — and the desk obeyed it while this dialog drew both sizes under
// every page size, as zeroes. The placeholder is the other half: 0 is how
// Frappe says "not set" here, and a page 0mm wide is not a page.
test('the custom page sizes belong to Custom', async ({ page, baseURL }) => {
  await signIn(page, baseURL)
  await page.goto('/one/')
  await page.locator('[data-slot="settings-link"]').click()
  await page.locator('[data-slot="settings-tab-printing"]').click()
  await page.getByText('Page size').waitFor()

  const size = page.getByRole('combobox').first()
  await expect(page.getByText('Custom width (mm)')).toBeHidden()

  await size.click()
  await page.getByRole('option', { name: 'Custom', exact: true }).click()
  await expect(page.getByText('Custom width (mm)')).toBeVisible()
  await expect(page.getByPlaceholder('210')).toBeVisible()

  await size.click()
  await page.getByRole('option', { name: 'A4', exact: true }).click()
  await expect(page.getByText('Custom width (mm)')).toBeHidden()
})

// The letter head the Printing tab's "Print with the letter head" actually
// uses. It was settable only from a switch three clicks inside the editor,
// while the formats list directly above offered a one-click Make default —
// and ERPNext ships three letter heads and flags none, so a workspace could
// have the switch on and a blank band at the top of every page.
test('a letter head is made the default from the list, and it sticks', async ({
  page,
  baseURL,
}) => {
  await signIn(page, baseURL)
  const open = async () => {
    await page.goto('/one/')
    await page.locator('[data-slot="settings-link"]').click()
    await page.locator('[data-slot="settings-tab-print-formats"]').click()
    await page.locator('[data-slot="letter-head"]').first().waitFor()
  }
  await open()

  // Whichever is not the default today — the fixture keeps whatever the last
  // run left, so the test may not assume which one that is.
  const other = page
    .locator('[data-slot="letter-head"]')
    .filter({ has: page.getByRole('button', { name: 'Make default' }) })
    .last()
  const name = (await other.locator('span').first().innerText()).trim()

  // Anchored: ERPNext's three ship as "Company Letterhead", "… - Grey" and
  // "… Report", so the first is a prefix of the other two.
  const exactly = (one) => new RegExp(`^${one.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`)
  const heads = page.locator('[data-slot="letter-head"]')

  await other.getByRole('button', { name: 'Make default' }).click()
  const row = heads.filter({ has: page.getByText(exactly(name)) })
  await expect(row.getByText('Default', { exact: true })).toBeVisible()

  // Exactly one *letter head* is the default — the formats list above carries
  // a Default badge of its own, so this is scoped to these rows. Frappe's own
  // `on_update` clears the others, and two defaults is a letter head nobody
  // can predict.
  await expect(heads.getByText('Default', { exact: true })).toHaveCount(1)

  // And it survives a reload, which is the half a local `ref` would fake.
  await open()
  await expect(
    heads.filter({ has: page.getByText(exactly(name)) })
      .getByText('Default', { exact: true }),
  ).toBeVisible()
})
