"""What the settings-panel geometry classes compensate for, pinned.

`apps/oneapp/frontend/src/modules/onespace/components/settings/geometry.js`
reflows frappe-ui's settings panels for a phone: `px-[4.4rem]` padding with no
responsive variant becomes a 1rem gutter, and the footer frappe-ui does not
ship gets written here.

There used to be four more, and they were about the *dialog* — a vertical nav
capped at 38vh, a panel column that refused to shrink below its widest table.
The dialog is gone: the panels are tabs on One's Configuration page, which has
its own tab strip and its own column, so those four went with it and so did the
half of this file that pinned them.

A compensation keyed to values that have since changed is worse than none: it
either stops applying or fights something new, and either way silently. So
these read the installed package and fail when the thing being compensated for
is gone — at which point geometry.js should be deleted, not adjusted.
"""

import re

import pytest

from frappe_ui_api import needs_frappe_ui, ROOT, UI_SRC

# Nothing here can be checked without the library it reads.
pytestmark = needs_frappe_ui()

# One set of panels, on the tenant app, for both audiences. The control plane
# used to have a second copy of this over its own Single; it hands its groups to
# these through `onespace_settings_groups` now.
SETTINGS_SRC = ROOT / "apps/oneapp/frontend/src/modules/onespace/components/settings"
GEOMETRY = SETTINGS_SRC / "geometry.js"
#: Where a panel is mounted now that there is no dialog.
PAGE = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/Configuration.vue"
SETTINGS = UI_SRC / "components/SettingsDialog"


def source(name: str) -> str:
    path = SETTINGS / name
    assert path.exists(), f"{path} is gone — SettingsDialog was restructured"
    return path.read_text()


def test_the_compensation_is_expressed_as_fallthrough_classes():
    """Everything is reachable through the library's own components.

    An earlier version was a stylesheet block keyed to `[role='tablist']` —
    markup frappe-ui never published as an API, matching any dialog that
    happened to contain tabs. Nothing is in CSS now: with the dialog gone,
    there is no element the library renders itself that no prop, slot or class
    can reach.
    """
    geometry = GEOMETRY.read_text()
    for name in ("PANEL_HEADER", "PANEL_BODY", "PANEL_FOOTER"):
        assert f"export const {name}" in geometry, f"{name} is gone"

    css = (ROOT / "apps/oneapp/frontend/src/index.css").read_text()
    assert "role='tablist'" not in css, (
        "the stylesheet is matching on a role again — scope it to our own marker"
    )
    assert "settings-dialog" not in css, (
        "the dialog is gone; a rule scoped to its marker matches nothing"
    )


@pytest.mark.parametrize("component", ["SettingsHeader.vue", "SettingsBody.vue"])
def test_panel_padding_is_still_a_fixed_desktop_value(component):
    """70.4px a side leaves 249px of a 390px phone, so labels wrap per word."""
    text = source(component)
    assert "px-[4.4rem]" in text, f"{component} no longer uses px-[4.4rem]"
    assert not re.search(r"(sm|md|lg):px-", text), (
        f"{component} gained a responsive padding — drop the matching constant "
        f"in {GEOMETRY.name} rather than layering on top of it"
    )


def test_the_body_padding_is_only_reachable_through_the_viewport():
    """SettingsBody puts its padding on the ScrollArea viewport, not its root.

    That is why PANEL_BODY is an arbitrary variant on `data-slot` rather than a
    plain `!px-4`: a class on SettingsBody lands on the ScrollArea root, which
    is not the padded element.
    """
    assert 'viewport-class="px-[4.4rem]' in source("SettingsBody.vue")
    viewport = (UI_SRC / "components/ScrollArea/ScrollArea.vue").read_text()
    assert 'data-slot="scroll-area-viewport"' in viewport
    assert "scroll-area-viewport" in GEOMETRY.read_text()


def test_every_panel_pins_its_own_header_body_and_actions():
    """A Save button inside SettingsBody scrolls away on a phone exactly when
    the form is long enough to need it."""
    offenders = []
    for path in SETTINGS_SRC.glob("*.vue"):
        text = path.read_text()
        if "<SettingsHeader" in text and ":class=\"PANEL_HEADER\"" not in text:
            offenders.append(f"{path.name}: SettingsHeader without PANEL_HEADER")
        if "<SettingsBody" in text and ":class=\"PANEL_BODY\"" not in text:
            offenders.append(f"{path.name}: SettingsBody without PANEL_BODY")
        # A panel's primary action belongs in the pinned footer, not the body.
        body = text[text.index("<SettingsBody"):text.index("</SettingsBody>")] if "<SettingsBody" in text else ""
        if 'label="Save"' in body:
            offenders.append(f"{path.name}: Save is inside the scrolling body")
    assert not offenders, "; ".join(offenders)


def test_the_footer_sits_after_the_body_so_it_pins_without_positioning():
    """SettingsPanel is a flex column and SettingsBody takes flex-1."""
    panel = source("SettingsPanel.vue")
    assert "flex min-h-0 flex-1 flex-col" in panel
    assert "min-h-0 flex-1" in source("SettingsBody.vue")

    form = (SETTINGS_SRC / "SettingsFields.vue").read_text()
    assert form.index("</SettingsBody>") < form.index("PANEL_FOOTER")


def test_wide_content_is_still_clipped_rather_than_scrolled():
    """SettingsBody's ScrollArea is vertical-only, and reka-ui then sets the
    viewport `overflow-x: hidden` — so a wide table is clipped, not scrolled.

    Nothing in a panel is that wide any more: the catalogue panels that were
    (plans, regions, spaces, the AI models table) are operator *screens* now,
    rendered in the grid pane that owns both its scrollbars. This still pins
    the upstream default, because a panel that grows one is on its own again.
    """
    scroll_area = (UI_SRC / "components/ScrollArea/ScrollArea.vue").read_text()
    assert "orientation: 'vertical'" in scroll_area, "ScrollArea's default changed"
    assert "orientation !== 'horizontal'" in scroll_area


