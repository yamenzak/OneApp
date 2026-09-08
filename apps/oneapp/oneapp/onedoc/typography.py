"""How a document is set, in the one place both halves of it can read.

There are two renderings of every document and they have to agree. One is the
editor, laying prose out inside a page-width column so somebody can see where
the pages break; the other is this file's CSS, laid out by the print engine so
the pages actually break there. If the two are set in different type they break
in different places, and a paged document that repaginates the moment you print
it is worse than one that never claimed to be paged.

So the numbers are here once. They are Tailwind Typography's `prose-sm` — which
is what the editor has always used — written out as plain CSS, because the
exported file is opened where Tailwind is not. The editor keeps the class; this
is the same scale beside it, and `DocEditor.vue` names this file.

The face is the deliberate part. A paged document is set in the system sans
rather than the app's Inter, on screen and on paper alike, because Inter is a
web font this file cannot carry and a page that reflows on the way to the
printer is exactly what this is here to prevent.
"""

#: The stack, and the only place it is written down. `DocEditor.vue` reads it
#: back through `docs/typography.font_stack`.
FONT_STACK = '-apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'

SERIF_STACK = 'Georgia, Cambria, "Times New Roman", Times, serif'
MONO_STACK = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'

#: The three the page-setup dialog offers, by the key it stores.
FACES = {"": FONT_STACK, "serif": SERIF_STACK, "mono": MONO_STACK}

#: What "tight", "normal" and "loose" mean, as a multiple of the font size.
#: "normal" is `prose-sm`'s own leading rather than `leading-relaxed`, because
#: `prose-sm` sets line-height on the element it is on and the leading class
#: sits on the wrapper above it — which is why picking a line spacing used to
#: change nothing at all. The editor now sets these three inline, where they
#: win, and reads them from `lib/paper/setup.js`.
LEADING = {"tight": 1.5, "normal": 1.7142857, "loose": 2}

BASE_PX = 14


def sheet(settings: dict | None = None) -> str:
    """The whole type scale, for one document's face and leading."""
    settings = settings or {}
    face = FACES.get(settings.get("font") or "", FONT_STACK)
    leading = LEADING.get(settings.get("spacing") or "normal", LEADING["normal"])

    return f"""
body {{ font-family: {face}; font-size: {BASE_PX}px; line-height: {leading};
       color: #1f2933; }}
p {{ margin: 1.1428571em 0; }}
h1 {{ font-size: 2.1428571em; line-height: 1.2; margin: 0 0 0.8em;
     font-weight: 800; }}
h2 {{ font-size: 1.4285714em; line-height: 1.4; margin: 1.6em 0 0.8em;
     font-weight: 700; }}
h3 {{ font-size: 1.2857143em; line-height: 1.5555556; margin: 1.5555556em 0 0.4444444em;
     font-weight: 600; }}
h4 {{ font-size: 1em; line-height: 1.4285714; margin: 1.4285714em 0 0.5714286em;
     font-weight: 600; }}
ul, ol {{ margin: 1.1428571em 0; padding-left: 1.5714286em; }}
li {{ margin: 0.2857143em 0; }}
blockquote {{ margin: 1.3333333em 0; padding-left: 1.1111111em;
             border-left: 3px solid #d9dde2; color: #52606d; font-style: italic; }}
hr {{ margin: 2.8571429em 0; border: 0; border-top: 1px solid #d9dde2; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.8571429em;
        line-height: 1.6666667; margin: 1.1428571em 0; }}
td, th {{ border: 1px solid #d9dde2; padding: 0.5714286em; text-align: left;
         vertical-align: top; }}
th {{ font-weight: 600; }}
img {{ max-width: 100%; height: auto; }}
pre {{ background: #f5f7fa; padding: 0.8571429em 1.1428571em; overflow-x: auto;
      border-radius: 6px; font-size: 0.8571429em; line-height: 1.7142857;
      margin: 1.7142857em 0; }}
code {{ font-family: {MONO_STACK}; font-size: 0.8571429em; }}
a {{ color: #1a56db; text-decoration: underline; }}
[dir=rtl] td, [dir=rtl] th {{ text-align: right; }}
[dir=rtl] blockquote {{ padding-left: 0; padding-right: 1.1111111em;
                       border-left: 0; border-right: 3px solid #d9dde2; }}
[dir=rtl] ul, [dir=rtl] ol {{ padding-left: 0; padding-right: 1.5714286em; }}
"""


def font_stack(settings: dict | None = None) -> str:
    """Just the face, for the editor's inline style."""
    return FACES.get((settings or {}).get("font") or "", FONT_STACK)
