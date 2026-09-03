import { chromium } from '@playwright/test'
const BASE = 'http://space.localhost:8001'
const OUT = '/tmp/claude-0/-home-user-OneApp/f17f9bdc-82ac-5f86-8ab5-67163311ded4/scratchpad/shots'
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' })
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('response', (r) => r.status() >= 400 && errors.push(`${r.status()} ${r.url()}`))
await page.request.post(`${BASE}/api/method/login`, { form: { usr: 'Administrator', pwd: 'Dev-Loop-2026!x' } })

await page.goto(`${BASE}/one/space/rua?screen=projects&record=PROJ-0063`)
await page.locator('[data-slot="showcase"]').waitFor({ timeout: 40000 })
await page.waitForTimeout(3000)
await page.screenshot({ path: `${OUT}/plus-rail.png` })

const before = await page.locator('[data-slot="showcase-child"]').count()
await page.locator('[data-slot="showcase-add-child"]').click()
await page.waitForTimeout(2500)
await page.screenshot({ path: `${OUT}/plus-dialog.png` })

// Fill the one thing a project needs, and save.
await page.getByRole('textbox', { name: 'Project Name' }).first().fill('ZZ Rail probe ' + Date.now())
await page.getByRole('button', { name: 'Create', exact: true }).click()
await page.waitForTimeout(4000)
await page.screenshot({ path: `${OUT}/plus-after.png` })
console.log('URL', page.url())
console.log('children before', before, 'after', await page.locator('[data-slot="showcase-child"]').count())
console.log('ERRORS', JSON.stringify(errors.slice(0, 6)))
await browser.close()
