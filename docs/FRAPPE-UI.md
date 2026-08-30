# frappe-ui: what we read, what we changed, what holds it

A page-by-page pass over [ui.frappe.io/docs](https://ui.frappe.io/docs) against
both SPAs — the tenant workspace (OneSpace), the operator console (OneAdmin),
customer self-service, and signup.

**Version.** `1.0.0-beta.55`, the newest published `beta`. npm's `latest` tag
still points at `0.1.278` — the v0 line — which is why v0 API shapes kept
appearing in this codebase and why the docs and most examples online describe a
different library. `scripts/check_frappe_ui.py` reports whether a newer beta is
out; a test asserts the installed version matches the pin, because every other
guard reads its declarations out of `node_modules` and would otherwise validate
against a version we do not ship.

**How these guards work.** Almost none of them encode a rule I typed in. They
read the installed package — prop and slot declarations, string-literal unions,
the CSS Tailwind actually emitted, the settings dialog's own class names — and
compare our source against it. That is deliberate: a pinned list of rules rots
the moment upstream changes, and the failure mode of this library is silence.
An unknown prop becomes a fallthrough attribute, an unknown slot never renders,
a retired token emits no CSS. Nothing throws. Only a comparison catches it.

---

## Getting Started

| Page | Read | Found | Applied | Guarded |
| --- | --- | --- | --- | --- |
| Introduction | ✅ | Its example uses the v0 `createResource` API | — | — |
| Getting Started | ✅ | Node ≥ 20.19; `ignore_csrf` for the dev proxy | Already met | Versions pinned identically across apps |
| **Migration from v0** | ✅ | **Retired tokens emitting no CSS**: `rounded`, `rounded-lg`, `bg-surface-white` — square corners and transparent cards on the launcher, account, signup, billing and PackCard | Official renames applied from `migrate-tokens-v2.js`, not typed from the guide | `test_design_tokens.py` — every class our source writes must emit CSS |
| Changelog | ✅ | Only Calendar/experimental changes | — | — |

The codemod's typography correction was **not** run: it shifts `text-lg` → `text-md`
for apps coming from pre-beta.11, and our classes were written against beta.55 —
the same ones frappe-ui's own components use. The scale really does have an `md`
between `base` and `lg`.

## Foundations

| Page | Read | Found | Applied | Guarded |
| --- | --- | --- | --- | --- |
| Tailwind Setup | ✅ | `content` must include the library's globs | Already correct | `test_tailwind_lists_frappe_ui_content` |
| Base Colors | ✅ | Raw palette is not the design system | Clean | Raw palette classes banned |
| Semantic Colors | ✅ | ink / surface / outline swap with the theme | `text-blue-600` removed from the tenant 404 | `test_colours_come_from_semantic_tokens` |
| Chart Colors | ✅ | Charts only | — | — |
| Typography | ✅ | One ramp; merged size+weight tokens | `text-base font-medium` → `text-base-medium` | Token audit |
| Radius | ✅ | **Named aliases removed in 1.0** | `rounded` → `rounded-4`, `-lg` → `-6` | Token audit |
| Elevation | ✅ | Shadows must pair with `surface-elevation-*`, not raw surfaces | We use no shadows | `test_shadows_pair_with_an_elevation_surface` |
| Focus Ring | ✅ | Global on `:focus-visible` | Nothing to do | — |

## Components

All 54 component pages were read. Their **API surface is guarded mechanically**
rather than page by page: `tests/frappe_ui_api.py` parses every component's
declarations — through all four forms frappe-ui uses, plus `defineModel` — and
five checks compare our markup against them.

| Check | Catches |
| --- | --- |
| Unknown props | `<Alert variant>` when the prop is `theme` |
| Unknown slots | `<Dialog #body-content>` when the body is the default slot |
| Content with nowhere to go | `<Alert>text</Alert>` when Alert has no default slot |
| Missing required props | `<ListRows>` with no `:items` |
| Values outside a union | `<Badge theme="orange">` |

Prose rules that needed work:

| Page | Found | Applied | Guarded |
| --- | --- | --- | --- |
| Icon | **A `lucide-*` class built from data emits no CSS.** `OneSpace Space.icon` was free text, so any icon an operator typed rendered as an empty box | Curated set in `scripts/app_icons.py` → SPA literals + doctype Select | Interpolated icon classes banned; every set member must emit CSS; the two lists must match |
| Icon | Reach for `<Icon>` only outside a component's icon prop | Three sidebars and UserMenu moved to `:icon` / `icon-right` | `test_icons_use_the_component_s_own_icon_prop` |
| Sidebar | The app owns the gutter; `SidebarItem` has none | Admin sidebar given a `ScrollArea` with `px-2` | Covered by the slot/prop checks |
| Sidebar | One slot, the default — no `#footer` | Footers rebuilt with `mt-auto` | Unknown-slot check |
| SettingsDialog | Panels compose `SettingsHeader` + `SettingsBody` | Correct | — |
| SettingsDialog | **Not responsive**: fixed `px-[4.4rem]`, a nav column capped at `38vh`, and Dialog's own `px-4 py-4` + `my-8` around a `w-screen h-[100dvh]` panel | Below `sm` the nav becomes a horizontally scrolling tab strip and panels take a 1rem gutter, a pinned header carries the close, and each panel's Save moves to a pinned footer — all fallthrough classes in `components/settings/geometry.js`, except Dialog's own padding and margin, which no prop or slot reaches and which stay a marker-scoped `index.css` rule | `test_settings_dialog_geometry.py` pins each upstream value |
| MobileNav / MobileShell | A grid bar of equal columns stops being readable past five; a sidebar holds twenty | Four primary destinations plus a trailing account avatar that opens a `BottomSheet` — the app switcher, overflow destinations, settings, appearance and log out — which is frappe-ui's own "You" example | `test_the_bottom_bar_leaves_a_slot_for_everything_else` |
| MobileNav / Sidebar | The bar and the sidebar were two declarations of one list, and had drifted to two names and two icons for the same page | One `lib/nav.js` per app, rendered by both | `test_navigation_is_declared_in_one_place`, `test_both_renderings_read_that_one_list` |
| list | Explicit grid tracks are absolute: three desktop columns leave ~60px for the identity column on a 390px phone | `useListColumns` declares each column's phone behaviour; what is dropped reappears beside or under the identity cell | `test_lists_wider_than_a_phone_declare_what_they_drop`, `test_a_dropped_column_takes_its_cell_with_it` |
| useColorScheme | Appearance was only reachable behind the settings dialog | One `lib/appearance.js` renders as a menu group, a `TabButtons` row, or a `Select` — the account menu on every surface, and the phone's sheet | `test_appearance_is_reachable_without_opening_settings` |
| Dropdown | `placement` removed in 1.0, warns in dev | → `side` + `align`, three surfaces | Unknown-prop check |
| ThemeSwitcher | **Deprecated** — use `Select` + `useColorScheme` | Replaced; dropped from the barrel | Deprecated components must stay out of the barrel |
| ThemeSwitcher | Theme flash without a pre-paint `data-theme` | Already handled | Shells checked against the composable's own key and attribute |
| list | `rowKey` is `ListRows`'; `ListHeaderCell`'s label is its default slot | Both fixed; row insets and heights set | Unknown-prop check |
| Alert / Badge / Button / Dialog / Tooltip / Progress / Avatar / FormControl / Select / Switch / Breadcrumbs / Tabs / Popover / HoverCard / BottomSheet / Rail / MobileNav / MobileShell / DesktopShell / PageHeader / ScrollArea / Spinner / Skeleton / Divider / ErrorMessage / KeyboardShortcut / Combobox / MultiSelect / Checkbox / Radio / Slider / Rating / DatePicker / TimePicker / Duration / Password / Textarea / TextInput / FormLabel / FileUploader / Tree / ContextMenu / ItemListRow / LoadingIndicator / LoadingText / TabButtons / FrappeUIProvider / Toast / KeyboardShortcutsDialog | Read; either already correct or unused | — | API guards apply regardless |

## Charts, Molecules, Experimental

| Section | Read | Status |
| --- | --- | --- |
| Charts (16 pages) | ✅ | Unused — no chart surface yet |
| Molecules / List | ✅ | In use; geometry and identity fixed |
| Molecules / Editor | ✅ | Unused |
| Experimental (Overview, Accordion, Calendar, CodeEditor, CommandPalette, ListView, MultiEmailInput) | ✅ | Unused, and deliberately so — parked components carry no stability promise |
| Legacy components | ✅ | We import none; the barrel test and ESLint bans already prevent it |

## Data Fetching and Resources

| Page | Read | Found | Applied | Guarded |
| --- | --- | --- | --- | --- |
| useCall | ✅ | Options are fixed; `enabled` is not one | Wrapped as `useResource` / `useAction` | `test_frappe_ui_calls.py` reads useCall's own option list |
| useList | ✅ | **Recommended layer; we hand-rolled it** on `frappe.client.get_list` — and named our helper `useList`, shadowing it | `useDocList` wraps the real one | `frappe.client.*` banned outside the data layer |
| useDoc | ✅ | Shared document store; reactive `name` | `useDocument` wraps it | ditto |
| useDoctype | ✅ | Independent submits per write | `useDocWrites` wraps it | ditto |
| useNewDoc | ✅ | For draft forms | Not needed yet | — |
| Resource / List Resource / Document Resource | ✅ | The v0 API — supported through 1.x, not recommended | Not used | ESLint blocks direct imports |

## Other

| Page | Read | Found | Applied | Guarded |
| --- | --- | --- | --- | --- |
| Icons | ✅ | See Components above | Curated set | 3 checks |
| Utilities | ✅ | **`dayjsLocal` needs `systemTimezone`**; plain `dayjs` reads a stored datetime as local | Boot ships the site zone; main.js configures it; invoice dates converted | Bare `dayjs()` banned in `.vue`; controllers and entry points checked |
| Composables | ✅ | `usePageMeta`, `useColorScheme` | Both in use correctly | — |
| Directives | ✅ | `vFocus`, `vOnOutsideClick` | `vFocus` in use | — |
| Vite Plugin | ✅ | Owns proxy, build paths, boot injection; `frappeTypes` is TS-only | Plugin in use | `test_vite_config_uses_the_frappe_ui_plugin` |
| VitePress theme | ✅ | For docs sites | Not applicable | — |

---

## Keeping up

```sh
python3 scripts/check_frappe_ui.py   # is a newer beta out?
python3 scripts/token_audit.py       # any class that emits no CSS?
python3 -m pytest tests/             # everything above
```

On an upgrade the order matters: bump the pin in `scripts/gen_frontend.py`,
regenerate, `npm install`, then run the suite. The guards read the new package,
so a renamed prop, a retired token or a changed slot surfaces as a test failure
instead of as a blank region on a page.
