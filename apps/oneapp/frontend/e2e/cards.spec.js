// The grid: the same records as the list, each drawn as a card.
//
// A board and a grid are one card twice — the mapping from a row to what is on
// its card is shared, and only the arrangement differs. What is checked here is
// the half that would otherwise be believed rather than seen: that the grid
// renders real records, that the gear over it asks the card question rather
// than the column one, and that a field chosen for a grid card is fetched even
// when it is not a column anybody is looking at.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const CARD = '[data-oneapp-card]'

const openGrid = async (page) => {
  await page.goto('/one/space/zzmock?screen=tasks&type=grid')
  await page.locator(CARD).first().waitFor({ timeout: 15_000 })
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a grid draws one card per record', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openGrid(page)

  // A whole page of them, in the order the list is sorted by — a grid is the
  // same rows arranged differently, not a different set of rows.
  expect(await page.locator(CARD).count()).toBeGreaterThan(3)

  const card = page.locator(CARD, { hasText: 'Book the van for Thursday' })
  await expect(card).toBeVisible()

  // A card is a link to its record, and clicking one opens it.
  await card.click()
  await expect(
    page.locator('[data-slot="record-pane"]').getByText('Book the van for Thursday').first(),
  ).toBeVisible()
  expectNoRealErrors(errors)
})

test('a card is three bands, and the last one is a control', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openGrid(page)

  const card = page.locator(CARD, { hasText: 'Book the van for Thursday' })
  await expect(card).toBeVisible()

  // The meta band: when it last moved, how many have said something, who it is
  // on, and whether this one is yours. The list shows the rest at the end of
  // every row, and a card that drops them says less than the list it came from.
  //
  // Faces rather than ids, and the page resolves them in one query rather than
  // one per card — the fixture puts two people on this one so the stack is a
  // stack.
  await expect(card.locator('[data-slot="row-assignee"]')).toHaveCount(2)

  const heart = card.getByRole('button', { name: 'Add to favourites' })
  await expect(heart).toBeVisible()

  // And it is a real control rather than a picture of one: pressing it
  // favourites the record without opening it.
  await heart.click()
  await expect(page.locator('[data-slot="record-pane"]')).toHaveCount(0)
  const off = card.getByRole('button', { name: 'Remove from favourites' })
  await expect(off).toBeVisible()

  // Put it back, so the fixture is where it was for every other spec.
  await off.click()
  await expect(card.getByRole('button', { name: 'Add to favourites' })).toBeVisible()
  expectNoRealErrors(errors)
})

test('the title is the keyboard way into a card', async ({ page }) => {
  await openGrid(page)

  // The tile is a click surface, which a keyboard cannot reach — so the title
  // inside it is a button, the same arrangement a list row uses. One press,
  // one record: the button stops the tile's own handler rather than letting
  // both fire.
  const card = page.locator(CARD, { hasText: 'Book the van for Thursday' })
  await card.getByRole('button', { name: 'Book the van for Thursday' }).click()
  await expect(
    page.locator('[data-slot="record-pane"]').getByText('Book the van for Thursday').first(),
  ).toBeVisible()
})

test('a grid over records with pictures is a gallery', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  // Contact declares an `image_field`, which is Frappe's own answer to "what
  // does one of these look like". A screen over it is a screen worth looking
  // at rather than reading, so every card leads with the picture.
  await page.goto('/one/space/zzmock?screen=people&type=grid')
  await page.locator(CARD).first().waitFor({ timeout: 15_000 })

  const ada = page.locator(CARD, { hasText: 'Ada Sinclair' })
  await expect(ada.locator('[data-slot="card-cover"] img')).toBeVisible()

  // The picture is fetched because the doctype says which field it is, not
  // because somebody listed that field as a column — this screen lists two,
  // and neither is the image.
  expect(await ada.locator('[data-slot="card-cover"] img').getAttribute('src'))
    .toContain('bubble-tea')

  // And a record with no picture keeps the frame: its initial, on the same
  // square. A gallery whose empty cards collapse is a gallery that jumps every
  // time somebody uploads a photograph.
  const dev = page.locator(CARD, { hasText: 'Dev Okonjo' })
  await expect(dev.locator('[data-slot="card-cover"]')).toBeVisible()
  await expect(dev.locator('[data-slot="card-cover"] img')).toHaveCount(0)
  await expect(dev.locator('[data-slot="card-cover"]')).toContainText('D')
  expectNoRealErrors(errors)
})

test('a grid over records with no picture is not a gallery', async ({ page }) => {
  // ToDo declares no image field, so there is no picture to make the subject
  // and the grid stays the card it was. The alternative is a page of grey
  // squares with a letter in them, which is a gallery of nothing.
  await openGrid(page)
  await expect(page.locator('[data-slot="card-cover"]')).toHaveCount(0)
})

test('the gear over a grid asks what is on a card', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the settings gear is desktop chrome')
  const errors = collectConsoleErrors(page)
  await openGrid(page)

  await page.getByRole('button', { name: 'Card settings' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()

  // A grid has no buckets, so it is not asked which field to bucket by — that
  // question is what makes a board.
  await expect(page.getByLabel('Columns of')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'On each card' })).toBeVisible()
  expectNoRealErrors(errors)
})

test('a field chosen for a card is fetched even where no column shows it', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the settings gear is desktop chrome')
  await openGrid(page)

  const card = page.locator(CARD, { hasText: 'Book the van for Thursday' })
  await expect(card).toBeVisible()

  await page.getByRole('button', { name: 'Card settings' }).click()
  await page.getByRole('button', { name: 'On each card' }).click()
  await page.getByRole('option', { name: 'Due Date', exact: true }).click()
  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')

  // The one field chosen, and only it — not whatever the list happens to show.
  await expect(card).toContainText('Aug')
  await expect(card).not.toContainText('Medium')

  // And the board keeps its own card: the two are separate answers, because a
  // board card sits under a heading naming the field it is bucketed by.
  await page.goto('/one/space/zzmock?screen=tasks&type=board')
  await page.locator('[data-oneapp-column]').first().waitFor({ timeout: 15_000 })
  await expect(
    page.locator('[data-oneapp-column="Open"] article', {
      hasText: 'Book the van for Thursday',
    }),
  ).toContainText('Medium')
})
