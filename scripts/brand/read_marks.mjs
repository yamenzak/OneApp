/*
 * The marks, out of the page that draws them.
 *
 * The previous design page held sixteen SVGs as template literals, and
 * `gen_brand.py` read them line by line. This one does not: every mark is a
 * function over a shared chassis, a shared beacon and a superellipse solver,
 * and several pick between variants. Reading that with a regex would mean
 * re-implementing the geometry in Python and hoping the two agree — which is
 * the same mistake as transcribing the SVGs by hand, one level up.
 *
 * So the page's own code is run. Everything from `const COMMON_FILTERS` to the
 * end of the `ICONS_SYSTEM` array is the drawing; everything after it is the
 * workbench's DOM, which is not wanted and would not run here anyway. The
 * slice is evaluated in a `vm` context with no globals but `Math`, and the
 * registry is dumped as JSON on stdout.
 *
 *     node scripts/brand/read_marks.mjs [source.html]
 *
 * Called by `scripts/gen_brand.py`, which is the only thing that should call
 * it. It prints and writes nothing else.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import vm from 'node:vm'

const HERE = dirname(fileURLToPath(import.meta.url))
const SOURCE = process.argv[2] || join(HERE, 'marks.source.html')

const OPENS = 'const COMMON_FILTERS'
const REGISTRY = 'const ICONS_SYSTEM = ['

const page = readFileSync(SOURCE, 'utf8')

const from = page.indexOf(OPENS)
const at = page.indexOf(REGISTRY)
if (from < 0 || at < 0) {
  throw new Error('the page has been rewritten: no COMMON_FILTERS or no ICONS_SYSTEM')
}

// The array's own end, found by balancing brackets from the `[` rather than by
// looking for `];` — a mark's path data is full of both characters, and a
// search would stop at the first one inside a string.
const opened = page.indexOf('[', at)
let depth = 0
let closed = -1
for (let i = opened; i < page.length; i += 1) {
  const ch = page[i]
  if (ch === '`') {
    // Template literals hold `[` and `]` in path data. Skipped whole, nesting
    // ignored: the page has no `${}` containing a backtick.
    i = page.indexOf('`', i + 1)
    if (i < 0) throw new Error('unterminated template literal in the registry')
    continue
  }
  if (ch === '[') depth += 1
  else if (ch === ']') {
    depth -= 1
    if (depth === 0) { closed = i; break }
  }
}
if (closed < 0) throw new Error('the ICONS_SYSTEM array does not close')

const drawing = page.slice(from, closed + 1)

const context = vm.createContext({ Math, Array, Object, String, Number, JSON })
vm.runInContext(`${drawing};\nglobalThis.__read = ICONS_SYSTEM;\nglobalThis.__common = COMMON_FILTERS`, context, {
  filename: 'marks.source.html',
})

const found = context.__read.map((one) => ({
  id: one.id,
  name: one.name,
  role: one.role || '',
  category: one.category || '',
  palette: one.palette || '',
  form: one.form || '',
  desc: one.desc || '',
  svg: one.getSvg(),
}))

if (!found.length) throw new Error('read no marks')

// The shared block every mark inlines, handed over so the generator can tell a
// mark's own gradients from the four the whole suite carries. Read out of the
// context rather than restated here: a copy would be one more thing to keep in
// step with a page it cannot see.
const out = { common: context.__common, marks: found }
process.stdout.write(`${JSON.stringify(out, null, 2)}\n`)
