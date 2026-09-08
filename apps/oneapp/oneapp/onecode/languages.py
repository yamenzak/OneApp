"""Which languages OneCode knows, and what each one is called.

Top level rather than under `docs/` because `drive.kinds` needs it to decide a
`.py` is code, and `docs` imports `drive.kinds` — one import the other way and
the two packages deadlock on each other at load.

One list, because three surfaces ask the same question and a fourth is about to:
the Drive deciding a `.py` is code rather than a mystery file, `New > Code`
offering something to pick, the editor telling CodeMirror what to highlight, and
a `Code` field on a doctype naming its language in `options`.

Mirrored in `frontend/src/lib/files/languages.js`, and `tests/test_onecode.py`
reads both back — a language the server will create and the picker does not
offer is a file nobody can make, and one the picker offers and the server
refuses is a button that throws.

`highlight` is the key frappe-ui's `loadLanguage` takes, and it is empty far
more often than not. That is the honest state of it: CodeMirror ships a
language pack per language and frappe-ui lazily imports ten of them. Everything
else still opens, still numbers its lines, still saves its own bytes — it is
just not coloured. A file that cannot be opened at all would be the worse
answer, and it is the one we had.
"""

#: key -> (label, extension, highlight). The key *is* the extension for all but
#: the aliases below it, which exist because a person types `.yml` and a person
#: types `.yaml` and neither is wrong.
LANGUAGES = {
	"js": ("JavaScript", "js", "javascript"),
	"ts": ("TypeScript", "ts", "javascript"),
	"py": ("Python", "py", "python"),
	"sql": ("SQL", "sql", "sql"),
	"json": ("JSON", "json", "json"),
	"yaml": ("YAML", "yaml", "yaml"),
	"xml": ("XML", "xml", "xml"),
	"html": ("HTML", "html", "html"),
	"css": ("CSS", "css", "css"),
	"scss": ("SCSS", "scss", "scss"),
	"vue": ("Vue", "vue", "html"),
	# Markdown is in the catalogue because CodeMirror highlights it and a `.md`
	# opens in the same editor as a `.py`. It is not in `OFFERED`: `New` already
	# has a Markdown file under Write, and one product offering the same file
	# twice under two headings is a menu nobody trusts.
	"md": ("Markdown", "md", "markdown"),
	"sh": ("Shell", "sh", ""),
	"go": ("Go", "go", ""),
	"rs": ("Rust", "rs", ""),
	"java": ("Java", "java", ""),
	"php": ("PHP", "php", ""),
	"rb": ("Ruby", "rb", ""),
	"c": ("C", "c", ""),
	"cpp": ("C++", "cpp", ""),
	"toml": ("TOML", "toml", ""),
	"ini": ("INI", "ini", ""),
}

#: Extensions that mean one of the above. Not in `LANGUAGES` because the picker
#: should offer one YAML and not two, and `New > Code` has to write one of them.
ALIASES = {
	"yml": "yaml",
	"jsx": "js",
	"tsx": "ts",
	"htm": "html",
	"sass": "scss",
	"bash": "sh",
	"zsh": "sh",
	"cc": "cpp",
	"h": "c",
	"hpp": "cpp",
	"mjs": "js",
	"cjs": "js",
	"markdown": "md",
}

#: What `New > Code` puts in front of somebody. Everything the catalogue knows
#: except the ones `New` already offers by name.
NOT_OFFERED = ("md",)

#: Every extension that opens in OneCode, aliases included.
EXTENSIONS = tuple(LANGUAGES) + tuple(ALIASES)

#: The picker's keys, alphabetical by label — alphabetical rather than in the
#: order declared, because the declaration is ordered by how well each one is
#: supported and that is a fact about us, not something a person choosing Rust
#: should have to know.
OFFERED = tuple(sorted(
	(key for key in LANGUAGES if key not in NOT_OFFERED),
	key=lambda key: LANGUAGES[key][0].lower(),
))


def resolve(extension: str) -> str:
	"""The catalogue key for one extension, or "" for something else entirely."""
	key = (extension or "").lower().lstrip(".")
	key = ALIASES.get(key, key)
	return key if key in LANGUAGES else ""


def highlight_for(extension: str) -> str:
	"""What CodeMirror should colour this as, or "" for no highlighting."""
	key = resolve(extension)
	return LANGUAGES[key][2] if key else ""


def label_for(extension: str) -> str:
	"""What to call this language on screen, or the bare extension."""
	key = resolve(extension)
	return LANGUAGES[key][0] if key else (extension or "").lower().lstrip(".")


def is_code(file_name: str) -> bool:
	name = (file_name or "").rsplit("?", 1)[0]
	if "." not in name:
		return False
	return bool(resolve(name.rsplit(".", 1)[-1]))
