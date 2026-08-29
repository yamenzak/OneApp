// Visual checks against a real local site, not a mocked one.
//
// The bugs this exists to catch — an empty list, a dialog that will not open, a
// control unreachable at one viewport — all render without throwing, so unit
// tests and a clean build say nothing about them. Only looking does.
import { defineConfig, devices } from '@playwright/test'

// The image ships one Chromium build and this runner expects another;
// `playwright install` is disabled here, so point at what exists rather than
// letting it try to download a build it will never get.
const CHROMIUM =
  process.env.ONEAPP_CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const launchOptions = { executablePath: CHROMIUM }

export default defineConfig({
  testDir: './e2e',
  // One worker: these drive a single shared site, and parallel logins race on
  // the same session.
  workers: 1,
  reporter: [['list']],
  timeout: 45_000,
  use: {
    baseURL: process.env.ONEAPP_BASE_URL || 'http://localhost:8000',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], launchOptions } },
    // The screenshot that started this was a phone: no sidebar, so anything
    // that lives only there is unreachable.
    { name: 'mobile', use: { ...devices['Pixel 7'], launchOptions } },
  ],
})
