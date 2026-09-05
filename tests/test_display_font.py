"""The one face in the product that is not the interface face.

Three ways a webfont goes wrong quietly, and all three end with the page
rendering in the fallback and nobody noticing: the file is not shipped, the
`@font-face` does not point at it, or the licence that lets us ship it at all is
not beside it. None of those throw, and a heading in the wrong font looks like a
heading.

The fourth way — declared, shipped, and never actually downloaded by a browser —
is `showcase.spec.js`, because only a browser can answer it.
"""

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "apps/oneapp/frontend"
FONTS = FRONTEND / "src/assets/fonts"
CSS = FRONTEND / "src/index.css"

# The family name the token and the `@font-face` rules both have to agree on.
FAMILY = "OneSpace Display"

# One file per script. Latin is what nearly every title is; Arabic is there
# because the product is sold where the correspondence is bilingual, and a face
# with no Arabic makes an Arabic title fall silently back to the UI font.
FILES = ("anton-latin.woff2", "reem-kufi-arabic.woff2")

LICENCES = ("OFL-Anton.txt", "OFL-ReemKufi.txt")


@pytest.mark.parametrize("name", FILES)
def test_the_font_is_shipped(name):
    found = FONTS / name
    assert found.exists(), f"{name} is declared in index.css and not in the repo"
    # woff2's magic number. A file that git or a download truncated is still a
    # file, and the browser's answer to one is the fallback face.
    assert found.read_bytes()[:4] == b"wOF2", f"{name} is not a woff2"


@pytest.mark.parametrize("name", LICENCES)
def test_the_licence_travels_with_it(name):
    found = FONTS / name
    assert found.exists(), f"{name} is missing — OFL 1.1 requires it beside the font"
    assert "SIL Open Font License" in found.read_text()


def test_every_face_is_declared_and_pointed_at_a_file_that_exists():
    css = CSS.read_text()
    faces = re.findall(r"@font-face\s*\{([^}]*)\}", css)
    ours = [one for one in faces if FAMILY in one]
    assert len(ours) == len(FILES), f"expected one @font-face per file, found {len(ours)}"

    for face in ours:
        url = re.search(r"url\('([^']+)'\)", face)
        assert url, "a face with no src"
        assert (CSS.parent / url.group(1)).resolve().exists(), url.group(1)
        # Without it both files download on any use of the family, which is the
        # Arabic subset fetched to render an English title.
        assert "unicode-range" in face, "a face with no unicode-range"
        # Without it a slow network renders nothing at all where the name goes.
        assert "font-display: swap" in face


def test_the_token_names_the_same_family():
    config = (FRONTEND / "tailwind.config.js").read_text()
    assert f"'{FAMILY}'" in config, "the `display` family and the @font-face disagree"
    # A fallback stack, not one name: `swap` shows the fallback first, and a
    # face with nowhere to fall back to shows the browser's default serif.
    assert "sans-serif" in config
