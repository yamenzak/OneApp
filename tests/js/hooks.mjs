/**
 * Run the SPA's own modules under node.
 *
 * Two things stop `import('…/lib/runtime/format.js')` working outside Vite:
 * the `@/` alias, which is a build-time setting, and `@/ui`, which pulls in
 * the whole component library and a browser. So this resolves the alias
 * against the bundle's `src`, and stubs the two modules that are about the
 * browser rather than about the logic under test — the barrel and the boot
 * payload.
 *
 * A stub is a risk: it is a second implementation of something, and the
 * second implementation is the one that never drifts *with* the first. Both
 * are kept to the minimum that lets the real code run, and `dayjsLocal` is
 * copied from frappe-ui's own `utils/dayjs.ts` rather than approximated — see
 * `tests/test_format.py::test_the_stub_matches_the_library`.
 */
import { pathToFileURL } from 'node:url'

const SRC = process.env.SPA_SRC
const MODULES = process.env.SPA_MODULES
const FORMATS = process.env.SPA_FORMATS || '{}'
const SYSTEM_TZ = process.env.SPA_SYSTEM_TZ || 'UTC'
const LOCAL_TZ = process.env.SPA_LOCAL_TZ || 'UTC'

const UI = 'spa-stub:ui'
const BOOT = 'spa-stub:boot'

export async function resolve(specifier, context, next) {
  if (specifier === '@/ui') return { url: UI, shortCircuit: true }
  if (specifier.startsWith('@/')) {
    if (specifier.endsWith('runtime/boot')) return { url: BOOT, shortCircuit: true }
    const rest = specifier.slice(2)
    const file = rest.endsWith('.js') || rest.endsWith('.vue') ? rest : `${rest}.js`
    return { url: new URL(file, pathToFileURL(`${SRC}/`)).href, shortCircuit: true }
  }
  // dayjs's ESM build imports `./constant` with no extension, which only a
  // bundler resolves. Node does not, so fill it in — for this package only,
  // because guessing at extensions anywhere else would hide a real typo.
  try {
    return await next(specifier, context)
  } catch (error) {
    if (error?.code !== 'ERR_MODULE_NOT_FOUND' || !specifier.startsWith('.')) throw error
    for (const tail of ['.js', '/index.js']) {
      try {
        return await next(specifier + tail, context)
      } catch { /* try the next shape */ }
    }
    throw error
  }
}

export async function load(url, context, next) {
  if (url === UI) {
    return { format: 'module', shortCircuit: true, source: `
      import _dayjs from '${MODULES}/dayjs/esm/index.js'
      import utc from '${MODULES}/dayjs/esm/plugin/utc/index.js'
      import timezone from '${MODULES}/dayjs/esm/plugin/timezone/index.js'
      import relativeTime from '${MODULES}/dayjs/esm/plugin/relativeTime/index.js'
      import customParseFormat from '${MODULES}/dayjs/esm/plugin/customParseFormat/index.js'
      _dayjs.extend(utc)
      _dayjs.extend(timezone)
      _dayjs.extend(relativeTime)
      _dayjs.extend(customParseFormat)
      export const dayjs = _dayjs
      // frappe-ui's own, from utils/dayjs.ts.
      export function dayjsLocal(value) {
        if (!value) return _dayjs().tz(${JSON.stringify(LOCAL_TZ)})
        return _dayjs.tz(value, ${JSON.stringify(SYSTEM_TZ)}).tz(${JSON.stringify(LOCAL_TZ)})
      }
    ` }
  }
  if (url === BOOT) {
    return { format: 'module', shortCircuit: true, source: `
      export const formats = ${FORMATS}
      export const systemTimezone = ${JSON.stringify(SYSTEM_TZ)}
      export default { formats, systemTimezone }
    ` }
  }
  return next(url, context)
}
