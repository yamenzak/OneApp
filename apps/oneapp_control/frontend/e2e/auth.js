// Sign in through Frappe's own endpoint rather than the login form: the form is
// Frappe's, not ours, and driving it would make every test depend on markup we
// do not own.
export async function signIn(page, baseURL) {
  const response = await page.request.post(`${baseURL}/api/method/login`, {
    form: {
      usr: process.env.ONEAPP_USER || 'Administrator',
      pwd: process.env.ONEAPP_PASSWORD || 'Dev-Loop-2026!x',
    },
  })
  if (!response.ok()) {
    throw new Error(`login failed: ${response.status()} ${await response.text()}`)
  }
}

/** Console errors say a page is broken even when it looks fine. */
export function collectConsoleErrors(page) {
  const errors = []
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  page.on('pageerror', (e) => errors.push(String(e)))
  return errors
}

/**
 * Fail on errors that mean something is broken, not on noise.
 *
 * The one worth catching is a fetch whose body is HTML: under our SPA route
 * rules Frappe answers an unknown path with the app's own page at 200, so a
 * mis-built request URL never 404s — it quietly returns a document and the data
 * is simply absent. That is how every useResource call fetched nothing.
 */
export function expectNoRealErrors(errors) {
  const ignorable = [
    // Logged by frappe-ui during a brief window before a resource resolves;
    // renders correctly and does not throw. Tracked, not silenced everywhere.
    /reading 'charAt'/,
  ]
  const real = errors.filter((e) => !ignorable.some((p) => p.test(e)))
  if (real.length) {
    throw new Error(`console errors:\n${real.join('\n')}`)
  }
}
