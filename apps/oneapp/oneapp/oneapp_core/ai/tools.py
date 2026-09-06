"""A Python function a model may call, and the schema it is described by.

Derived from `frappe/flow_client` (`flow/lib/tool.py`), AGPL-3.0, Copyright (c)
2026 Frappe Technologies and contributors. The schema builder is theirs and is a
solved problem: reading a signature's type hints into JSON Schema is fiddly in
exactly the same ways every time — `Annotated` for descriptions, `Optional` for
what may be left out, `Literal` for a closed list.

Two things are ours. There is no pydantic here — Flow validates arguments with
`validate_call`, and the coercion below is the small part of that we need, so
`tests/` can import this module without a bench. And a tool is declared with the
`system` half of an `@ai_feature` rather than beside a provider, because a
workspace never picks a model here either.

The thing worth being careful about is not the schema. It is that a model chose
these arguments: `chat/toolbox.py` is where every tool goes through
`frappe.has_permission` before it reads anything, and nothing in this module
grants access to anything.
"""

import inspect
import json
import types
import typing
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

#: How much of an exception a tool raised the model is shown. Long enough to be
#: actionable, short enough that a stack trace cannot become the prompt.
ERROR_LIMIT = 500

PRIMITIVES = {
	str: {"type": "string"},
	int: {"type": "integer"},
	float: {"type": "number"},
	bool: {"type": "boolean"},
}


@dataclass
class Tool:
	name: str
	description: str
	parameters: dict
	func: Any
	#: Arguments the caller supplies rather than the model — the asking user,
	#: the space being asked about. They are not in the schema, so the model
	#: cannot name one, which is the whole reason they are separate.
	bound: dict = field(default_factory=dict)

	def __call__(self, **kwargs):
		return self.func(**{**coerce(self.parameters, kwargs), **self.bound})

	def bind(self, **bound) -> "Tool":
		"""The same tool with context filled in. Used per request, not per site."""
		return Tool(self.name, self.description, self.parameters, self.func,
		            {**self.bound, **bound})

	def declare(self) -> dict:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description,
				"parameters": self.parameters,
			},
		}


def tool(func=None, *, name: str = "", description: str = ""):
	"""Make a function callable by a model.

	The docstring is the description, because a tool whose description is
	written twice is a tool whose description goes stale in one of the two
	places. The first line is what the model reads; keep it a sentence.
	"""

	def wrap(fn):
		return Tool(
			name=name or fn.__name__,
			description=description or (inspect.getdoc(fn) or "").strip(),
			parameters=build_schema(fn),
			func=fn,
		)

	return wrap(func) if func is not None else wrap


def build_schema(func) -> dict:
	"""JSON Schema for a function's arguments, read off its type hints.

	A parameter is required unless it has a default or its type admits None.
	`Annotated[str, "what this is"]` puts the description in the schema, which
	is the difference between a model guessing what `query` means and being
	told.
	"""
	signature = inspect.signature(func)
	hints = get_type_hints(func, include_extras=True)

	properties, required = {}, []
	for arg, parameter in signature.parameters.items():
		if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
			continue
		if arg in ("self", "cls") or arg.startswith("_"):
			continue

		hint, described = _annotated(hints.get(arg, Any))
		hint, optional = _optional(hint)

		schema = _schema_for(hint)
		if described:
			schema["description"] = described
		properties[arg] = schema

		if parameter.default is inspect.Parameter.empty and not optional:
			required.append(arg)

	schema = {"type": "object", "properties": properties}
	if required:
		schema["required"] = required
	return schema


def coerce(schema: dict, arguments: dict) -> dict:
	"""Bend a model's arguments into the shapes the signature declared.

	Models return `"3"` for an integer and `"true"` for a boolean often enough
	that refusing them means refusing a call that was right in every way that
	mattered. Anything that will not convert is passed through untouched and the
	function raises normally — a wrong argument should fail in the tool, where
	the message says what was wrong, not in a coercion helper.
	"""
	properties = schema.get("properties") or {}
	out = {}
	for key, value in (arguments or {}).items():
		want = (properties.get(key) or {}).get("type")
		out[key] = _as(want, value)
	return out


def _as(want, value):
	if want is None or value is None:
		return value
	try:
		if want == "integer" and not isinstance(value, bool):
			return int(value)
		if want == "number" and not isinstance(value, bool):
			return float(value)
		if want == "boolean" and isinstance(value, str):
			return value.strip().lower() in ("1", "true", "yes")
		if want == "string" and not isinstance(value, str):
			return value if isinstance(value, (dict, list)) else str(value)
		if want == "array" and isinstance(value, str):
			parsed = json.loads(value)
			return parsed if isinstance(parsed, list) else value
		if want == "object" and isinstance(value, str):
			parsed = json.loads(value)
			return parsed if isinstance(parsed, dict) else value
	except (TypeError, ValueError):
		return value
	return value


def _annotated(hint):
	metadata = getattr(hint, "__metadata__", None)
	if metadata is None:
		return hint, None
	described = next((m for m in metadata if isinstance(m, str)), None)
	return getattr(hint, "__origin__", hint), described


def _optional(hint):
	if get_origin(hint) not in (Union, types.UnionType):
		return hint, False
	args = get_args(hint)
	if type(None) not in args:
		return hint, False
	rest = tuple(a for a in args if a is not type(None))
	if len(rest) == 1:
		return rest[0], True
	return (Union[rest] if rest else Any), True


def _schema_for(hint) -> dict:
	if hint is Any or hint is object or hint is None:
		return {}
	if hint in PRIMITIVES:
		return dict(PRIMITIVES[hint])
	if hint is dict:
		return {"type": "object"}
	if hint is list:
		return {"type": "array"}

	origin, args = get_origin(hint), get_args(hint)

	if origin in (list, tuple, set, frozenset, typing.List, typing.Tuple, typing.Set):
		return {"type": "array", "items": _schema_for(args[0]) if args else {}}
	if origin in (dict, typing.Dict):
		return {"type": "object"}
	if origin is Literal:
		return _enum(list(args))
	if origin in (Union, types.UnionType):
		return {"anyOf": [_schema_for(a) for a in args]}
	if isinstance(hint, type) and issubclass(hint, Enum):
		return _enum([member.value for member in hint])
	return {}


def _enum(values) -> dict:
	kinds = {type(v) for v in values}
	if kinds == {str}:
		return {"type": "string", "enum": values}
	if kinds == {bool}:
		return {"type": "boolean", "enum": values}
	if kinds <= {int}:
		return {"type": "integer", "enum": values}
	if kinds <= {int, float}:
		return {"type": "number", "enum": values}
	return {"enum": list(values)}


def run(one: Tool, arguments: dict) -> str:
	"""Call a tool and return what the model is shown, error included.

	A raised exception is a result, not a failure of the run: the model asked
	for a record that does not exist, or a doctype nobody may read, and the
	useful thing is for it to be told so and try something else. The alternative
	— aborting the conversation — turns a typo into a dead session.
	"""
	try:
		return serialize(one(**(arguments or {})))
	except Exception as e:  # noqa: BLE001 — the message goes to the model, not the log
		return json.dumps({"error": str(e)[:ERROR_LIMIT]})


def serialize(result) -> str:
	if isinstance(result, str):
		return result
	if result is None:
		return ""
	try:
		return json.dumps(result, default=str)
	except (TypeError, ValueError):
		return str(result)
