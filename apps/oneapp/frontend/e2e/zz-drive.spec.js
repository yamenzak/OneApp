import { test } from '@playwright/test'
import { signIn } from './auth.js'

test('drive', async ({ page, baseURL }) => {
  await signIn(page, baseURL)
  await page.goto('/one/files')
  await page.waitForTimeout(1500)
  await page.screenshot({ path: '/tmp/claude-0/-home-user-OneApp/f17f9bdc-82ac-5f86-8ab5-67163311ded4/scratchpad/drive-list.png' })
  await page.getByRole('button', { name: 'Show as a grid' }).click()
  await page.waitForTimeout(900)
  await page.screenshot({ path: '/tmp/claude-0/-home-user-OneApp/f17f9bdc-82ac-5f86-8ab5-67163311ded4/scratchpad/drive-grid.png' })
})
