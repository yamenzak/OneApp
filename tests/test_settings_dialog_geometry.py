"""What the settings-dialog geometry classes compensate for, pinned.

`apps/oneapp_control/frontend/src/components/settings/geometry.js` reflows
frappe-ui's SettingsDialog for a phone: hard-coded values with no responsive
variant — a vertical nav capped at 38vh, `px-[4.4rem]` panel padding — become a
horizontally scrolling tab strip and a 1rem gutter.

A compensation keyed to values that have since changed is worse than none: it
either stops applying or fights something new, and either way silently. So these
read the installed package and fail when the thing being compensated for is
gone — at which point geometry.js should be deleted, not adjusted.
"""

import re

import pytest

from frappe_ui_api import ROOT, UI_SRC

SETTINGS_SRC = ROOT / "apps/oneapp_control/frontend/src/components/settings"
GEOMETRY = SETTINGS_SRC / "geometry.js"
SHELL = SETTINGS_SRC / "SettingsShell.vue"
SETTINGS = UI_SRC / "components/SettingsDialog"


def source(name: str) -> str:
    path = SETTINGS / name
    assert path.exists(), f"{path} is gone — SettingsDialog was restructured"
    return path.read_text()


def test_the_compensation_is_expressed_as_fallthrough_classes():
    """Everything reachable through the library's own components is a class.

    The earlier version was a stylesheet block keyed to `[role='tablist']` —
    markup frappe-ui never published as an API, matching any dialog that
    happened to contain tabs. What survives in CSS is only what no prop, slot or
    class can reach: the padding and margin Dialog puts on elements it renders
    itself.
    """
    geometry = GEOMETRY.read_text()
    for name in ("TAB_STRIP", "TAB_GROUP", "TAB_ITEM", "PANEL_HEADER", "PANEL_BODY"):
        assert f"export const {name}" in geometry, f"{name} is gone"

    css = (ROOT / "apps/oneapp_control/frontend/src/index.css").read_text()
    assert "role='tablist'" not in css, (
        "the stylesheet is matching on a role again — scope it to our own marker"
    )
    assert "[data-oneapp='settings-dialog']" in css, "the marker scope is gone"
    assert "data-oneapp=\"settings-dialog\"" in SHELL.read_text(), (
        "nothing carries the marker the stylesheet keys off"
    )


def test_the_dialog_chrome_the_stylesheet_neutralises_is_still_there():
    """`w-screen h-[100dvh]` inside `px-4 py-4` and `my-8` is a full-screen
    dialog that starts 32px down and ends 48px past the bottom — which is where
    the pinned Save footer went."""
    dialog = (UI_SRC / "components/Dialog/Dialog.vue").read_text()
    assert "px-4 py-4" in dialog, "Dialog's scroll container is no longer padded"
    assert "my-8" in dialog, "Dialog's content no longer carries a vertical margin"
    for hook in ("dialog-scroll-container", "dialog-content"):
        assert hook in dialog, f"Dialog no longer carries .{hook}"
    settings = source("SettingsDialog.vue")
    assert "h-[100dvh]" in settings and "w-screen" in settings


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


def test_the_nav_is_still_a_capped_vertical_column():
    """The shape TAB_STRIP turns into a row: 38vh of a tall phone is 320px of
    nav before any content, laid out as a column."""
    sidebar = source("SettingsSidebar.vue")
    assert "max-h-[38vh]" in sidebar, "SettingsSidebar's mobile height cap changed"
    assert "flex-col" in sidebar, "SettingsSidebar is no longer a column"
    assert "sm:max-h-none" in sidebar, "the cap is no longer mobile-only"


def test_the_nav_group_shape_the_strip_reflows_is_unchanged():
    """TAB_GROUP hides the heading and lays the items out along the strip, and
    addresses them positionally — so the two children have to still be there."""
    group = source("SettingsNavGroup.vue")
    assert group.count("<div") == 3, "SettingsNavGroup is no longer heading + items"
    assert "flex flex-col gap-0.5" in group, "the items row is no longer a column"
    assert 'class="flex h-7 items-center px-2' in group, "the heading changed shape"


def test_a_tab_is_still_full_width():
    assert "w-full" in source("SettingsNavItem.vue"), (
        "SettingsNavItem is no longer full-width, so TAB_ITEM has nothing to undo"
    )


def test_the_dialog_switches_layout_at_the_same_breakpoint_we_do():
    """geometry.js is written in `max-sm:` — one breakpoint, not two that can
    disagree about which layout is on screen."""
    dialog = source("SettingsDialog.vue")
    assert "sm:flex-row" in dialog and "flex-col" in dialog
    assert "md:flex-row" not in dialog, "the dialog moved to a different breakpoint"


def test_the_dialog_is_still_bare_and_so_renders_no_close_button():
    """`bare` skips Dialog's chrome, including its close button.

    Full-screen on a phone with no close button and no backdrop is a dead end,
    so SettingsShell adds one itself. If SettingsDialog stops passing `bare`, or
    starts rendering its own, ours becomes a duplicate.
    """
    assert re.search(r"<Dialog[^>]*\bbare\b", source("SettingsDialog.vue"), re.S)

    shell = SHELL.read_text()
    assert 'label="Close settings"' in shell, "the mobile close control is gone"
    assert "sm:hidden" in shell, "the close control should not double up on desktop"


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

    form = (SETTINGS_SRC / "SettingsForm.vue").read_text()
    assert form.index("</SettingsBody>") < form.index("PANEL_FOOTER")


def test_wide_content_owns_its_own_horizontal_scroller():
    """SettingsBody's ScrollArea is vertical-only, and reka-ui then sets the
    viewport `overflow-x: hidden` — so a wide table is clipped, not scrolled."""
    scroll_area = (UI_SRC / "components/ScrollArea/ScrollArea.vue").read_text()
    assert "orientation: 'vertical'" in scroll_area, "ScrollArea's default changed"
    assert "orientation !== 'horizontal'" in scroll_area

    catalogue = (SETTINGS_SRC / "CatalogueList.vue").read_text()
    assert "overflow-x-auto" in catalogue, "the wide table lost its scroller"


def test_a_panel_may_shrink_below_its_widest_child():
    """The scroller only scrolls if the panel is allowed to be narrower than it.

    SettingsPanel is a flex item of SettingsContent, and a flex item's
    `min-width` defaults to `auto` — it refuses to shrink below its content. So
    `overflow-x-auto` around a `min-w-[40rem]` table did not scroll: it stretched
    the panel to 787px inside a 412px phone, with a third of it unreachable and
    `document.scrollWidth` clean the whole time because the dialog clips what
    overflows. Every catalogue panel had it.

    Applied once, on SettingsContent, reaching its panels — so a new panel gets
    it without having to know.
    """
    from pathlib import Path

    for app in ("oneapp_control", "oneapp"):
        settings = Path(__file__).resolve().parents[1] / (
            f"apps/{app}/frontend/src/components/settings")

        geometry = (settings / "geometry.js").read_text()
        assert "[&>[role=tabpanel]]:min-w-0" in geometry, (
            f"{app}: PANEL_CONTENT no longer lets a panel shrink")

        shell = (settings / "SettingsShell.vue").read_text()
        assert 'SettingsContent :class="PANEL_CONTENT"' in shell, (
            f"{app}: SettingsContent is not carrying PANEL_CONTENT")
