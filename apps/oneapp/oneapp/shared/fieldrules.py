"""The doctype's own rules about its fields, evaluated on the server.

The twin of `modules/onespace/lib/screen/rules.js`, and it exists because that
file was the only one of the two. Frappe carries three rules —
`depends_on`, `mandatory_depends_on` and `read_only_depends_on` — the browser
honoured all three on the record form, and the server honoured none: `save`
builds its allowlist from the *static* `read_only` flag, so a field the form
locked could be written from a child-table grid, from an inline cell, or from
a script, and the save went through. `docs/UNIFICATION.md` §B5.

## Why this is a parser and not `frappe.safe_eval`

Two reasons, and the second is the one that decides it.

The expression is a string in the database, editable by anybody who can write
a Property Setter. `safe_eval` is built for exactly that risk and would be a
reasonable answer to it on its own.

But the expression is written in the *desk's* dialect, which is JavaScript:
`&&`, `||`, `!`, `===`, `.length`. Handing that to a Python evaluator gives a
syntax error on the common case and — worse — the wrong answer on the
uncommon one, because `1 && 2` is 2 in JavaScript and a NameError in Python.
Two evaluators that disagree are worse than one, since a field would lock in
the browser and stay writable here.

So this is the same grammar, parsed the same way, and `tests/test_field_rules.py`
runs one corpus of expressions through both and asserts identical answers.

Supported, exactly as the browser supports it: field paths, string, number,
boolean and null literals, array literals, `== != === !== > >= < <=`,
`&& || !`, membership, `.length`, and brackets. Nothing that calls anything,
and nothing that assigns. Anything outside the grammar is no rule at all,
which is the same answer the browser gives.
"""

import re

NUMBER = re.compile(r"^\d+(\.\d+)?")
IDENT = re.compile(r"^[A-Za-z_$][\w$]*")

#: Longest first, so `===` is not read as `==` followed by `=`.
PUNCT = ("===", "!==", "==", "!=", ">=", "<=", "&&", "||",
         "(", ")", "[", "]", ",", "!", ">", "<", ".")

EQUAL = ("==", "===")
UNEQUAL = ("!=", "!==")


class _Unreadable(Exception):
	"""The expression is outside the grammar. Not an error — an absence."""


def _tokenize(source: str):
	"""The expression, in pieces. `None` when it contains something unknown."""
	tokens = []
	rest = source.strip()
	while rest:
		if rest[0] in " \n\t":
			rest = rest[1:]
			continue
		if rest[0] in "\"'":
			quote = rest[0]
			end = rest.find(quote, 1)
			if end == -1:
				return None
			tokens.append(("value", rest[1:end]))
			rest = rest[end + 1:]
			continue
		number = NUMBER.match(rest)
		if number:
			text = number.group(0)
			tokens.append(("value", float(text) if "." in text else int(text)))
			rest = rest[len(text):]
			continue
		word = IDENT.match(rest)
		if word:
			name = word.group(0)
			if name == "true":
				tokens.append(("value", True))
			elif name == "false":
				tokens.append(("value", False))
			elif name in ("null", "undefined"):
				tokens.append(("value", None))
			elif name == "in":
				tokens.append(("op", "in"))
			else:
				tokens.append(("name", name))
			rest = rest[len(name):]
			continue
		found = next((one for one in PUNCT if rest.startswith(one)), None)
		if not found:
			return None
		tokens.append(("op", found))
		rest = rest[len(found):]
	return tokens


def _loose_equal(left, right) -> bool:
	"""JavaScript's `==`, for the two cases a docfield rule actually hits.

	A Check is 0 or 1 in the database and `false` in a rule; a Select's value
	is a string beside a number often enough. Everything else falls through to
	Python's own equality, which agrees with JavaScript's for like types.
	"""
	if left is None or right is None:
		return left is None and right is None
	if isinstance(left, bool) or isinstance(right, bool):
		return bool(left) == bool(right)
	if isinstance(left, (int, float)) and isinstance(right, str):
		return _number(right) == left
	if isinstance(right, (int, float)) and isinstance(left, str):
		return _number(left) == right
	return left == right


def _number(text: str):
	try:
		return float(text) if "." in text else int(text)
	except (TypeError, ValueError):
		# `1 == "abc"` is false in JavaScript, and NaN compares equal to
		# nothing — returning a value no number equals is the same answer.
		return object()


def _order(op: str, left, right) -> bool:
	"""`> >= < <=`, and `false` where the two cannot be compared.

	JavaScript coerces and answers false for a pair that will not coerce;
	Python raises. Answering false is the browser's behaviour and the safe one
	— a rule that cannot be decided is not a rule that locks a field.
	"""
	try:
		if op == ">":
			return left > right
		if op == ">=":
			return left >= right
		if op == "<":
			return left < right
		return left <= right
	except TypeError:
		return False


class _Reader:
	def __init__(self, tokens, scope):
		self.tokens = tokens
		self.at = 0
		self.scope = scope

	def peek(self):
		return self.tokens[self.at] if self.at < len(self.tokens) else None

	def eat(self, value) -> bool:
		token = self.peek()
		if token and token[0] == "op" and token[1] == value:
			self.at += 1
			return True
		return False

	def parse_or(self):
		left = self.parse_and()
		while self.eat("||"):
			# Both sides are read whatever the left one said: the browser's
			# reader does the same, because short-circuiting would leave
			# tokens behind and a trailing token means "unreadable".
			right = self.parse_and()
			left = _truthy(left) or _truthy(right)
		return left

	def parse_and(self):
		left = self.parse_not()
		while self.eat("&&"):
			right = self.parse_not()
			left = _truthy(left) and _truthy(right)
		return left

	def parse_not(self):
		if self.eat("!"):
			return not _truthy(self.parse_not())
		return self.comparison()

	def comparison(self):
		left = self.primary()
		token = self.peek()
		if not token or token[0] != "op":
			return left
		if token[1] in EQUAL:
			self.at += 1
			return _loose_equal(left, self.primary())
		if token[1] in UNEQUAL:
			self.at += 1
			return not _loose_equal(left, self.primary())
		if token[1] in (">", ">=", "<", "<="):
			op = token[1]
			self.at += 1
			return _order(op, left, self.primary())
		if token[1] == "in":
			self.at += 1
			holder = self.primary()
			if isinstance(holder, list):
				return any(_loose_equal(left, one) for one in holder)
			return str(left) in str("" if holder is None else holder)
		return left

	def primary(self):
		if self.eat("("):
			value = self.parse_or()
			self.eat(")")
			return value
		if self.eat("["):
			items = []
			while not self.eat("]"):
				if self.at >= len(self.tokens):
					raise _Unreadable("unclosed list")
				items.append(self.parse_or())
				self.eat(",")
			return items

		token = self.peek()
		if not token:
			raise _Unreadable("expression ended early")
		self.at += 1
		if token[0] == "value":
			return token[1]
		if token[0] != "name":
			raise _Unreadable(f"unexpected {token[1]}")

		# A path: `doc.status`, or `status` on its own, and `.length` on the end.
		value = self.scope.get(token[1])
		while self.eat("."):
			part = self.peek()
			if not part or part[0] != "name":
				raise _Unreadable("a path needs a name after the dot")
			self.at += 1
			if part[1] == "length":
				value = 0 if value is None else len(value)
			elif value is None:
				value = None
			elif isinstance(value, dict):
				value = value.get(part[1])
			else:
				value = getattr(value, part[1], None)
		return value


def _truthy(value) -> bool:
	"""JavaScript's truthiness, which differs from Python's in one place worth
	naming: `"0"` is true in JavaScript and every non-empty string is."""
	if isinstance(value, str):
		return value != ""
	return bool(value)


def evaluate(rule, doc) -> bool | None:
	"""One rule, against one record. `None` when the rule cannot be read.

	`None` rather than `False` so a caller can tell "no" from "no idea" —
	and the callers here treat "no idea" as no rule, which is what the
	browser does and what keeps the two in step.
	"""
	text = str(rule or "").strip()
	if not text:
		return None

	values = dict(doc or {})
	# Frappe's shorthand: a bare fieldname means "when this is filled in".
	if not text.startswith("eval:"):
		word = IDENT.match(text)
		if word and word.group(0) == text:
			return _truthy(values.get(text))
		return None

	tokens = _tokenize(text[5:])
	if not tokens:
		return None
	try:
		reader = _Reader(tokens, {"doc": values})
		value = reader.parse_or()
	except _Unreadable:
		return None
	# Trailing tokens mean the grammar did not cover the whole expression, and
	# half an expression is not an answer.
	if reader.at != len(tokens):
		return None
	return _truthy(value)


def locked(field, doc) -> bool:
	"""Whether `read_only_depends_on` locks this field on this record.

	The one question the save path asks. A rule that cannot be read does not
	lock anything — the same answer the browser gives, and the safe one: the
	static `read_only` flag and the permlevel are checked separately and are
	not affected by this.
	"""
	rule = getattr(field, "read_only_depends_on", None) or (
		field.get("read_only_depends_on") if isinstance(field, dict) else None
	)
	return evaluate(rule, doc) is True
