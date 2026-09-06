/**
 * Bundle the inbound worker into the control-plane app.
 *
 * The worker imports `postal-mime`, so what Cloudflare's API accepts is one
 * file rather than this directory. And it has to land *inside*
 * `apps/oneapp_control/` rather than beside its source: Frappe Cloud installs
 * that app on its own, so anything outside it is not there at runtime, and the
 * control plane is what uploads the script.
 *
 * The stamp beside it is the sha256 of every source that went in, so
 * `tests/test_worker_bundle.py` can fail when somebody edits the worker and
 * forgets to run this.
 *
 * Run: cd workers/email-inbound && npm install && npm run build
 */

import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { build } from 'esbuild'

const here = dirname(fileURLToPath(import.meta.url))
const out = join(here, '../../apps/oneapp_control/oneapp_control/cloudflare/worker')

const SOURCES = ['src/index.js', 'src/routing.js', 'package.json']

mkdirSync(out, { recursive: true })

await build({
  entryPoints: [join(here, 'src/index.js')],
  bundle: true,
  format: 'esm',
  platform: 'neutral',
  target: 'es2022',
  legalComments: 'none',
  outfile: join(out, 'email-inbound.js'),
})

const stamp = createHash('sha256')
for (const name of SOURCES) {
  stamp.update(name)
  stamp.update(readFileSync(join(here, name)))
}
writeFileSync(join(out, 'email-inbound.sha256'), `${stamp.digest('hex')}\n`)

console.log('bundled into', out)
