/**
 * The doctype's own rules about its fields, evaluated against a record.
 *
 * Frappe carries three of them — `depends_on`, `mandatory_depends_on` and
 * `read_only_depends_on` — and they are what make a form feel like a form: a
 * field appears when another says so, becomes required, or stops being
 * editable. Each is either a bare fieldname, meaning "when this is filled in",
 * or `eval:` followed by an expression about `doc`.
 *
 * The desk runs that expression as JavaScript. This does not, and the reason is
 * where the string comes from: it is a row in a database, editable by anyone
 * who can write a Property Setter, and `new Function` on it would turn "can
 * customise a form" into "can run code in every reader's browser". So the
 * expression is parsed — a small grammar that covers what these rules actually
 * say — and anything outside it is treated as no rule at all rather than
 * guessed at.
 *
 * What is supported: field paths (`doc.status`), string, number, boolean and
 * null literals, array literals, `== != === !== > >= < <=`, `&& || !`,
 * membership (`doc.status in ['Open', 'Closed']`), `.length`, and brackets.
 * Nothing that calls anything, and nothing that assigns.
 */

const NUMBER = /^\d+(\.\d+)?/
const IDENT = /^[A-Za-z_$][\w$]*/
const PUNCT = ['===', '!==', '==', '!=', '>=', '<=', '&&', '||', '(', ')', '[', ']', ',', '!', '>', '<', '.']

/** The expression, in pieces. Returns null when it contains something unknown. */
function tokenize(source) {
  const tokens = []
  let rest = source.trim()
  while (rest) {
    if (rest[0] === ' ' || rest[0] === '\n' || rest[0] === '\t') {
      rest = rest.slice(1)
      continue
    }
    if (rest[0] === '"' || rest[0] === "'") {
      const quote = rest[0]
      const end = rest.indexOf(quote, 1)
      if (end === -1) return null
      tokens.push({ type: 'value', value: rest.slice(1, end) })
      rest = rest.slice(end + 1)
      continue
    }
    const number = NUMBER.exec(rest)
    if (number) {
      tokens.push({ type: 'value', value: Number(number[0]) })
      rest = rest.slice(number[0].length)
      continue
    }
    const word = IDENT.exec(rest)
    if (word) {
      const name = word[0]
      if (name === 'true') tokens.push({ type: 'value', value: true })
      else if (name === 'false') tokens.push({ type: 'value', value: false })
      else if (name === 'null' || name === 'undefined') tokens.push({ type: 'value', value: null })
      else if (name === 'in') tokens.push({ type: 'op', value: 'in' })
      else tokens.push({ type: 'name', value: name })
      rest = rest.slice(name.length)
      continue
    }
    const punct = PUNCT.find((one) => rest.startsWith(one))
    if (!punct) return null
    tokens.push({ type: 'op', value: punct })
    rest = rest.slice(punct.length)
  }
  return tokens
}

const EQUAL = ['==', '===']
const UNEQUAL = ['!=', '!==']
const ORDER = { '>': (a, b) => a > b, '>=': (a, b) => a >= b, '<': (a, b) => a < b, '<=': (a, b) => a <= b }

class Reader {
  constructor(tokens, scope) {
    this.tokens = tokens
    this.at = 0
    this.scope = scope
  }

  peek() {
    return this.tokens[this.at]
  }

  eat(value) {
    const token = this.peek()
    if (token && token.type === 'op' && token.value === value) {
      this.at += 1
      return true
    }
    return false
  }

  or() {
    let left = this.and()
    while (this.eat('||')) left = this.and() || left
    return left
  }

  and() {
    let left = this.not()
    while (this.eat('&&')) {
      const right = this.not()
      left = left && right
    }
    return left
  }

  not() {
    if (this.eat('!')) return !this.not()
    return this.comparison()
  }

  comparison() {
    const left = this.primary()
    const token = this.peek()
    if (!token || token.type !== 'op') return left
    if (EQUAL.includes(token.value)) {
      this.at += 1
      // Loose on purpose: a Check is 0 or 1 in the database and `false` in a
      // rule, and a Select's value is a string beside a number often enough.
      return left == this.primary()
    }
    if (UNEQUAL.includes(token.value)) {
      this.at += 1
      return left != this.primary()
    }
    if (ORDER[token.value]) {
      this.at += 1
      return ORDER[token.value](left, this.primary())
    }
    if (token.value === 'in') {
      this.at += 1
      const list = this.primary()
      return Array.isArray(list) ? list.includes(left) : String(list ?? '').includes(left)
    }
    return left
  }

  primary() {
    if (this.eat('(')) {
      const value = this.or()
      this.eat(')')
      return value
    }
    if (this.eat('[')) {
      const items = []
      while (!this.eat(']')) {
        if (this.at >= this.tokens.length) throw new SyntaxError('unclosed list')
        items.push(this.or())
        this.eat(',')
      }
      return items
    }
    const token = this.peek()
    if (!token) throw new SyntaxError('expression ended early')
    this.at += 1
    if (token.type === 'value') return token.value
    if (token.type !== 'name') throw new SyntaxError(`unexpected ${token.value}`)

    // A path: `doc.status`, or `status` on its own, and `.length` on the end.
    let value = Object.prototype.hasOwnProperty.call(this.scope, token.value)
      ? this.scope[token.value]
      : undefined
    while (this.eat('.')) {
      const part = this.peek()
      if (!part || part.type !== 'name') throw new SyntaxError('a path needs a name after the dot')
      this.at += 1
      if (part.value === 'length') value = value == null ? 0 : value.length
      else value = value == null ? undefined : value[part.value]
    }
    return value
  }
}

/**
 * One rule, against one record. `null` when the rule cannot be read, which is
 * how a caller tells "no" from "no idea".
 */
export function evaluate(rule, doc) {
  const text = String(rule || '').trim()
  if (!text) return null
  // A bare fieldname is Frappe's shorthand for "when this is filled in".
  if (!text.startsWith('eval:')) {
    return IDENT.test(text) && IDENT.exec(text)[0] === text ? !!doc?.[text] : null
  }
  const tokens = tokenize(text.slice(5))
  if (!tokens || !tokens.length) return null
  try {
    const reader = new Reader(tokens, { doc: doc || {} })
    const value = reader.or()
    // Trailing tokens mean the grammar did not cover the whole expression, and
    // half an expression is not an answer.
    return reader.at === tokens.length ? !!value : null
  } catch {
    return null
  }
}

/**
 * How one field should render on this record: shown or not, required or not,
 * editable or not.
 *
 * A rule that cannot be read is no rule — the field behaves as the doctype
 * declared it without one. That is the least surprising of the three possible
 * answers, and it is safe: the server validates `reqd` and
 * `mandatory_depends_on` again on save, so a form that is wrong here produces
 * a worse error message rather than a worse record.
 */
export function fieldRules(field, doc) {
  const shown = evaluate(field?.depends_on, doc)
  const required = evaluate(field?.mandatory_depends_on, doc)
  const readOnly = evaluate(field?.read_only_depends_on, doc)
  return {
    hidden: shown === false,
    required: !!field?.reqd || required === true,
    readOnly: readOnly === true,
  }
}
