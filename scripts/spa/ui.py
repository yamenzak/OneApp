"""The component barrel both SPAs import from.

Nothing may import a frappe-ui component directly — `scripts/check_frappe_ui.py`
and the ESLint config together make `src/ui.js` the only door. That is what
makes "does frappe-ui already ship this?" a question with one answer rather than
one per page.
"""

from .spec import BANNER


# Components the design system sanctions. Adding one here is the deliberate act
# that makes it available to both apps at once.
UI_BARREL = BANNER + """
/**
 * The sanctioned frappe-ui surface.
 *
 * Both SPAs import from here rather than from 'frappe-ui' directly, so what the
 * product may use is one reviewable list instead of whatever each file reached
 * for. ESLint enforces it, and a test asserts this covers everything frappe-ui
 * exports — a component missing here is a component someone will hand-roll.
 *
 * Reach for a component before writing markup. A <div> with divide-y is not a
 * list; a <router-link> with an active class is not a sidebar item. They look
 * close in isolation and wrong beside everything else.
 */

export {
  // ----- Shell -----------------------------------------------------------
  // DesktopShell renders a PageHeaderTarget and a ScrollArea itself, so pages
  // teleport their header up with <PageHeader> rather than laying one out.
  DesktopShell,
  MobileShell,
  MobileNav,
  MobileNavItem,
  Rail,
  RailItem,
  ScrollArea,
  ScrollBar,

  // ----- Page header -----------------------------------------------------
  PageHeader,
  PageHeaderBase,
  PageHeaderTitle,
  PageHeaderBackButton,
  PageHeaderMobile,
  PageHeaderMobileTitle,
  PageHeaderTarget,

  // ----- Sidebar ---------------------------------------------------------
  Sidebar,
  SidebarItem,
  SidebarLabel,
  SidebarSection,
  SidebarHeader,
  SidebarCard,
  SidebarCollapseToggle,

  // ----- Settings --------------------------------------------------------
  // A whole family, so settings surfaces are composed rather than hand-built.
  SettingsDialog,
  SettingsSidebar,
  SettingsNavGroup,
  SettingsNavItem,
  SettingsBody,
  SettingsContent,
  SettingsPanel,
  SettingsHeader,
  SettingsRow,

  // ----- Structure -------------------------------------------------------
  Divider,
  Breadcrumbs,
  Tabs,
  TabList,
  TabTrigger,
  TabPanel,
  TabButtons,

  // ----- Actions ---------------------------------------------------------
  Button,
  Dropdown,
  ContextMenu,

  // ----- Form controls ---------------------------------------------------
  FormControl,
  FormLabel,
  TextInput,
  Textarea,
  Password,
  Select,
  Combobox,
  MultiSelect,
  Checkbox,
  Switch,
  Radio,
  RadioGroup,
  Slider,
  Rating,
  DatePicker,
  DateTimePicker,
  DateRangePicker,
  TimePicker,
  Duration,
  FileUploader,
  ErrorMessage,

  // ----- Feedback --------------------------------------------------------
  Alert,
  Badge,
  Progress,
  Spinner,
  LoadingIndicator,
  LoadingText,
  Skeleton,
  Tooltip,
  TooltipProvider,

  // ----- Overlays --------------------------------------------------------
  Dialog,
  Popover,
  HoverCard,
  BottomSheet,
  KeyboardShortcut,
  KeyboardShortcutsDialog,

  // ----- Display ---------------------------------------------------------
  Avatar,
  Icon,
  Tree,
  ItemListRow,

  // ----- Root provider ---------------------------------------------------
  FrappeUIProvider,

  // ----- Imperative ------------------------------------------------------
  toast,
  dialog,

  // ----- Composables -----------------------------------------------------
  usePageMeta,
  useColorScheme,
  useKeyboardShortcut,
  useShellScrolled,
  useFileUpload,

  // ----- Directives ------------------------------------------------------
  vFocus,
  vOnOutsideClick,

  // ----- Data and utilities ----------------------------------------------
  call,
  frappeRequest,
  setConfig,
  getConfig,
  upload,
  dayjs,
  dayjsLocal,
  debounce,
} from 'frappe-ui'

/**
 * The list family. A separate entry point in frappe-ui because it ships its own
 * structural CSS; re-exported here so pages have one import path.
 *
 * `List` takes grid track sizes via `columns` and handles dividers, selection
 * and the active row. Reach for it before writing a table or a stack of divs.
 */
export {
  List,
  ListHeader,
  ListHeaderCell,
  ListHeaderCellSort,
  ListRows,
  ListRow,
  ListCell,
  ListGroup,
} from 'frappe-ui/list'

/**
 * The rich-text editor. Its own entry point in frappe-ui because it ships the
 * ProseMirror stylesheet with it, so importing from here pulls both.
 *
 * One component covers two fieldtypes: `format` is 'html' | 'json' |
 * 'markdown', and Frappe's Text Editor and Markdown Editor differ only in
 * which of those they store. HTML Editor is *not* one of them — that is
 * Frappe's source editor, markup a person edits as markup, so it goes to
 * CodeEditor below.
 *
 * `Editor` is renderless — it owns the lifecycle and renders nothing — so the
 * building blocks come with it. `EditorContent` is the element ProseMirror
 * mounts on and the thing a person types into; without it the field is an
 * empty box.
 */
export {
  Editor,
  EditorContent,
  EditorFixedMenu,
  EditorBubbleMenu,
  RichTextKit,
  // The toolbar that matches the kit. frappe-ui ships three presets —
  // `minimalToolbar`, `commentToolbar`, `articleToolbar` — and a menu whose
  // buttons are not in the loaded extension list is a row of controls that do
  // nothing, so the pair is chosen together rather than separately.
  articleToolbar,
} from 'frappe-ui/editor'

/**
 * The code editor, and the one unstable thing in this barrel.
 *
 * `frappe-ui/experimental` carries no backward-compatibility promise, and this
 * is a deliberate bet: the alternative for Code, JSON and HTML Editor is a
 * plain textarea, which is a customer editing braces in a box with no bracket
 * matching. The bet is bounded — one entry point, three exports, wrapped by
 * FieldControl, so a breaking change touches one file — and it is checked:
 * `tests/frappe_ui_api.py` reads `experimental/` alongside `src/`, so these
 * props are verified against the source like every other component's.
 *
 * `loadLanguage` is a function rather than a component: CodeMirror's language
 * packs are dynamic imports, so a page with no code field pays for none of
 * them.
 */
export { CodeEditor, CodePreview, loadLanguage } from 'frappe-ui/experimental'

/**
 * The calendar, from the same unstable entry point and on the same terms.
 *
 * Month, week and day over a list of events, with the drag, the resize and the
 * click-a-cell-to-create already in it. It was in the root export before 1.0
 * and moved here as "parked" — exempt from the deprecation policy until a
 * redesigned calendar replaces it — which is the honest reason to take it: the
 * alternative is FullCalendar, a second date library and a second set of theme
 * rules, to end up with what is already installed. It is what Frappe Suite's
 * own calendar draws with.
 *
 * `CalendarColorMap` comes with it because an event's colour is a name from a
 * fixed set — amber, violet, pink, cyan, blue, orange, green — and anything
 * offering a choice of one needs the same list rather than a second copy.
 */
export { Calendar, CalendarColorMap } from 'frappe-ui/experimental'

/**
 * Charts, from frappe-ui's own entry point.
 *
 * Nine plots and four pieces of chrome, all echarts-backed. They are a separate
 * entry point in the library and stay one here — `frappe-ui/charts` also ships
 * the `--chart-*` colour ramps as a stylesheet, so importing from it is what
 * makes a plot follow the app's theme rather than echarts' defaults.
 *
 * The chrome is exported alongside the plots on purpose. A chart a screen draws
 * itself — a sparkline, a plot with an axis nothing here has — composes
 * ChartCard, ChartContainer, ChartLegend and ChartTooltip and reads as one of
 * the family; hand-rolling the card around it is how two charts on one page
 * come to have two different titles, two paddings and two empty states.
 */
export {
  AreaChart,
  BarChart,
  DonutChart,
  FunnelChart,
  HeatmapChart,
  LineChart,
  NumberCard,
  SankeyChart,
  ScatterChart,
  ChartCard,
  ChartContainer,
  ChartLegend,
  ChartTooltip,
} from 'frappe-ui/charts'
"""
