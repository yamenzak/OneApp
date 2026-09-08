/**
 * Which languages OneCode knows, and what each one is called.
 *
 * The SPA's copy of `oneapp_core/docs/languages.py`, and `tests/test_onecode.py`
 * reads the two back against each other: a language the picker offers and the
 * server refuses is a button that throws, and one the server will create and
 * the picker does not offer is a file nobody can make.
 *
 * `highlight` is the key frappe-ui's `loadLanguage` takes, and it is empty far
 * more often than not — CodeMirror ships a language pack per language and
 * frappe-ui lazily imports ten of them. Everything else still opens, still
 * numbers its lines and still saves its own bytes; it is just not coloured.
 */

//: extension -> [label, highlight]. The key is the extension.
export const LANGUAGES = {
  js: ['JavaScript', 'javascript'],
  ts: ['TypeScript', 'javascript'],
  py: ['Python', 'python'],
  sql: ['SQL', 'sql'],
  json: ['JSON', 'json'],
  yaml: ['YAML', 'yaml'],
  xml: ['XML', 'xml'],
  html: ['HTML', 'html'],
  css: ['CSS', 'css'],
  scss: ['SCSS', 'scss'],
  vue: ['Vue', 'html'],
  // Markdown is in the catalogue because CodeMirror highlights it and a `.md`
  // opens in the same editor as a `.py`. It is not offered by `New > Code`:
  // `New` already has a Markdown file under Write, and one product offering the
  // same file twice under two headings is a menu nobody trusts.
  md: ['Markdown', 'markdown'],
  sh: ['Shell', ''],
  go: ['Go', ''],
  rs: ['Rust', ''],
  java: ['Java', ''],
  php: ['PHP', ''],
  rb: ['Ruby', ''],
  c: ['C', ''],
  cpp: ['C++', ''],
  toml: ['TOML', ''],
  ini: ['INI', ''],
}

//: Extensions that mean one of the above. Not in `LANGUAGES` because the picker
//: should offer one YAML and not two.
export const ALIASES = {
  yml: 'yaml',
  jsx: 'js',
  tsx: 'ts',
  htm: 'html',
  sass: 'scss',
  bash: 'sh',
  zsh: 'sh',
  cc: 'cpp',
  h: 'c',
  hpp: 'cpp',
  mjs: 'js',
  cjs: 'js',
  markdown: 'md',
}

//: What `New > Code` puts in front of somebody. Everything the catalogue knows
//: except the ones `New` already offers by name.
export const NOT_OFFERED = ['md']

const clean = (extension) => String(extension || '').toLowerCase().replace(/^\./, '')

/** The catalogue key for one extension, or '' for something else entirely. */
export function resolveLanguage(extension) {
  const key = clean(extension)
  const found = ALIASES[key] || key
  return LANGUAGES[found] ? found : ''
}

/** What CodeMirror should colour this as, or '' for no highlighting. */
export function highlightFor(extension) {
  const key = resolveLanguage(extension)
  return key ? LANGUAGES[key][1] : ''
}

/** What to call this language on screen, or the bare extension. */
export function labelForLanguage(extension) {
  const key = resolveLanguage(extension)
  return key ? LANGUAGES[key][0] : clean(extension)
}

/** Whether a filename is one OneCode opens. */
export const isCode = (fileName) => {
  const name = String(fileName || '').split('?')[0]
  return name.includes('.') && !!resolveLanguage(name.split('.').pop())
}

/**
 * The picker's rows, alphabetical by label. Alphabetical rather than in the
 * order they were declared: the declaration is ordered by how well each one is
 * supported, which is a fact about us and not something a person choosing
 * "Rust" should have to know.
 */
export const languageOptions = () =>
  Object.entries(LANGUAGES)
    .filter(([key]) => !NOT_OFFERED.includes(key))
    .map(([key, [label]]) => ({ key, label }))
    .sort((a, b) => a.label.localeCompare(b.label))
