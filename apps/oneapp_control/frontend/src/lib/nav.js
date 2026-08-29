import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { setup } from './setup'
import { workspaces } from './customer'

/**
 * Every destination, declared once per surface.
 *
 * The sidebar and the phone's bottom bar are two renderings of one list, not
 * two lists. Declared separately they drift, and they did: the same page was
 * "Readiness" with a checklist icon in the sidebar and "Setup" with a gear in
 * the bottom bar, which reads as two different features and put a second gear
 * beside the settings dialog's.
 *
 * `primary: false` keeps an entry out of the bottom bar without moving it in
 * the sidebar — the bar has four slots before the account avatar, and the rest
 * land in the More sheet. `match` names the extra route names a section owns,
 * so a detail page keeps its parent highlighted.
 */
function adminItems() {
  return [
    {
      label: 'Tenants',
      icon: 'lucide-users',
      to: { name: 'Tenants' },
      match: ['Tenant'],
    },
    { label: 'Provisioning', icon: 'lucide-activity', to: { name: 'Jobs' } },
    { label: 'Shards', icon: 'lucide-server', to: { name: 'Shards' } },
    {
      label: 'Readiness',
      icon: 'lucide-list-checks',
      to: { name: 'Setup' },
      badge: setup.canProvision
        ? null
        : { theme: 'amber', label: String(setup.blockers.length) },
    },
  ]
}

function portalItems() {
  const workspace = workspaces.current
  if (!workspace) return []
  const at = (name) => ({ name, params: { workspace } })
  return [
    { label: 'Overview', icon: 'lucide-home', to: at('AccountOverview') },
    { label: 'Apps', icon: 'lucide-layout-grid', to: at('AccountApps') },
    { label: 'Billing', icon: 'lucide-credit-card', to: at('AccountBilling') },
    { label: 'People', icon: 'lucide-users', to: at('AccountTeam') },
    // Read far less often than the four above, and the bar only has four
    // slots. Both stay one tap away in the More sheet.
    { label: 'Plan', icon: 'lucide-layers', to: at('AccountPlan'), primary: false },
    { label: 'Domain', icon: 'lucide-globe', to: at('AccountDomain'), primary: false },
  ]
}

/**
 * The current surface's destinations, with `active` already resolved.
 *
 * Both sidebars and the shell call this, so there is exactly one place a
 * destination is named, iconed and ordered.
 */
export function useNav() {
  const route = useRoute()
  return computed(() => {
    const items = route.meta.surface === 'admin' ? adminItems() : portalItems()
    return items.map((item) => ({
      ...item,
      active: route.name === item.to.name || (item.match || []).includes(route.name),
    }))
  })
}
