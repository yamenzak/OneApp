/**
 * Which component draws each `panel` tab.
 *
 * The other half of the contract in `onespace/tabs.py`: the server says a tab
 * exists and who may open it, and this says what it looks like. A key on one
 * side with nothing on the other is a tab that renders as an empty panel —
 * silently, the way Vue does — so a test reads both lists and fails on either
 * gap.
 *
 * Its own module because there are two callers now. The dialog was the first
 * and the Configuration page is the second: the panels moved onto a *page*,
 * which is what gave them an address and what put a member's four beside the
 * tables of the space they are standing in. A copy of this map in the second
 * caller would be the exact divergence `docs/UNIFICATION.md` F1 is about —
 * the abstraction built at the second caller and abandoned at the third.
 */
import AppearanceSettings from '@/modules/onespace/components/settings/AppearanceSettings.vue'
import BooksSettings from '@/modules/onespace/components/settings/BooksSettings.vue'
import AiSettings from '@/modules/onespace/components/settings/AiSettings.vue'
import AlertSettings from '@/modules/onespace/components/settings/AlertSettings.vue'
import TemplateSettings from '@/modules/onespace/components/settings/TemplateSettings.vue'
import DomainSettings from '@/modules/onespace/components/settings/DomainSettings.vue'
import PeopleSettings from '@/modules/onespace/components/settings/PeopleSettings.vue'
import RoleSettings from '@/modules/onespace/components/settings/RoleSettings.vue'
import StorageSettings from '@/modules/onespace/components/settings/StorageSettings.vue'
import BackupSettings from '@/modules/onespace/components/settings/BackupSettings.vue'
import NamingSettings from '@/modules/onespace/components/settings/NamingSettings.vue'
import LegalSettings from '@/modules/onespace/components/settings/LegalSettings.vue'
import PrintingSettings from '@/modules/onespace/components/settings/PrintingSettings.vue'
import MailSettings from '@/modules/onespace/components/settings/MailSettings.vue'
import MailboxSettings from '@/modules/onespace/components/settings/MailboxSettings.vue'
import ProfileSettings from '@/modules/onespace/components/settings/ProfileSettings.vue'
import SecuritySettings from '@/modules/onespace/components/settings/SecuritySettings.vue'
import NotificationSettingsPanel from '@/modules/onespace/components/settings/NotificationSettingsPanel.vue'
import ConnectionSettings from '@/modules/onespace/components/settings/ConnectionSettings.vue'

export const PANELS = {
  profile: ProfileSettings,
  security: SecuritySettings,
  notifications: NotificationSettingsPanel,
  appearance: AppearanceSettings,
  mailbox: MailboxSettings,
  books: BooksSettings,
  'print-formats': PrintingSettings,
  legal: LegalSettings,
  naming: NamingSettings,
  mail: MailSettings,
  templates: TemplateSettings,
  alerts: AlertSettings,
  ai: AiSettings,
  domain: DomainSettings,
  people: PeopleSettings,
  roles: RoleSettings,
  storage: StorageSettings,
  backups: BackupSettings,
  connections: ConnectionSettings,
}

/**
 * The panels a *space* has, as opposed to the workspace.
 *
 * All three are keyed on a doctype — an alert is about one, a series names
 * one, a print format is drawn over one — so "this space's" is exactly "the
 * ones its screens show", and the space's Configuration page hands each of
 * them its space code. One's Configuration hands them nothing, which is the
 * workspace-wide answer they always gave.
 *
 * `onespace/configuration.py` appends these to every Configuration page, so a
 * space does not declare them: they are the engine's, like the page itself.
 * The list is here as well because the browser has to know which panels take
 * the prop — a `space` attribute falling through onto a panel that does not
 * declare it would land on its root element as invalid markup.
 */
export const SPACE_PANELS = ['alerts', 'naming', 'print-formats']
