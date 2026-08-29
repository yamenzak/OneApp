"""What the settings-dialog CSS override compensates for, pinned.

`apps/oneapp_control/frontend/src/index.css` corrects three hard-coded values in
frappe-ui's SettingsDialog that have no responsive variant. An override keyed to
values that have since changed is worse than no override: it either stops
applying or fights something new, and either way it does so silently.

So these read the installed package and fail when the thing being compensated
for is gone — at which point the override should be deleted, not adjusted.
"""

import re

import pytest

from frappe_ui_api import ROOT, UI_SRC

OVERRIDE = ROOT / "apps/oneapp_control/frontend/src/index.css"
SETTINGS = UI_SRC / "components/SettingsDialog"


def source(name: str) -> str:
    path = SETTINGS / name
    assert path.exists(), f"{path} is gone — SettingsDialog was restructured"
    return path.read_text()


def test_the_override_is_present():
    css = OVERRIDE.read_text()
    assert "dialog-scroll-container" in css and "role='tablist'" in css


@pytest.mark.parametrize("component", ["SettingsHeader.vue", "SettingsBody.vue"])
def test_panel_padding_is_still_a_fixed_desktop_value(component):
    """70.4px a side leaves 249px of a 390px phone, so labels wrap per word."""
    text = source(component)
    assert "px-[4.4rem]" in text, f"{component} no longer uses px-[4.4rem]"
    assert not re.search(r"(sm|md|lg):px-", text), (
        f"{component} gained a responsive padding — drop the override in "
        f"{OVERRIDE.name} rather than layering on top of it"
    )


def test_the_sidebar_still_takes_a_fixed_share_of_the_height():
    assert "max-h-[38vh]" in source("SettingsSidebar.vue"), (
        "SettingsSidebar's mobile height cap changed"
    )


def test_the_dialog_is_still_bare_and_so_renders_no_close_button():
    """`bare` skips Dialog's chrome, including its close button.

    Full-screen on a phone with no close button and no backdrop is a dead end,
    so SettingsShell adds one itself. If SettingsDialog stops passing `bare`, or
    starts rendering its own, ours becomes a duplicate.
    """
    assert re.search(r"<Dialog[^>]*\bbare\b", source("SettingsDialog.vue"), re.S)

    shell = (
        ROOT / "apps/oneapp_control/frontend/src/components/settings/SettingsShell.vue"
    ).read_text()
    assert 'label="Close settings"' in shell, "the mobile close control is gone"
    assert "sm:hidden" in shell, "the close control should not double up on desktop"


def test_the_dialog_hooks_the_override_keys_off_still_exist():
    dialog = (UI_SRC / "components/Dialog/Dialog.vue").read_text()
    for hook in ("dialog-scroll-container", "dialog-content"):
        assert hook in dialog, f"Dialog no longer carries .{hook}"
    viewport = (UI_SRC / "components/ScrollArea/ScrollArea.vue").read_text()
    assert 'data-slot="scroll-area-viewport"' in viewport
