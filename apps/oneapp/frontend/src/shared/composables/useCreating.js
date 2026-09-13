/**
 * Making a record from a screen.
 *
 * Three doors lead here and they want different things afterwards. The header's
 * New makes one of this screen's records and lands you in it. A board column's
 * New does the same with the column's status already filled in. And the plus on
 * a showcase's rail makes something that hangs off the record being read —
 * possibly of a different screen entirely — and must leave you where you were.
 *
 * Which is why `intoRail` is a flag rather than something inferred from the
 * preset: a board's New sets a preset too, and the two want opposite endings.
 */
import { computed, ref } from 'vue'

import { workspace } from '@/shared/lib/workspace'
import { KIND, withAt } from '@/shared/lib/url/at'

export function useCreating({ spaceCode, spec, route, router, reloadList }) {
  const showCreate = ref(false)
  // What the dialog opens with already filled in. Empty for the header's New.
  const preset = ref({})
  // Whether the dialog that is open was opened by the rail's plus.
  const intoRail = ref(false)
  // What the showcase's rail has been told to re-read. Bumped rather than
  // reloaded directly: a number travelling down as a prop is less machinery
  // than a handle travelling up.
  const childRevision = ref(0)

  /**
   * Which screen the dialog is filling in. Nearly always this one; the
   * exception is the rail, where what hangs off a record may be a different
   * screen and a dialog drawn from this spec would ask for the wrong fields.
   */
  const onto = ref(null)

  const createSpec = computed(() => onto.value || spec.value)
  const createScreen = computed(() => onto.value?.screen || spec.value?.screen || '')

  const create = () => {
    preset.value = {}
    onto.value = null
    intoRail.value = false
    showCreate.value = true
  }

  // New from somewhere that already knows part of the answer — a board column
  // header being the one today.
  const newWith = (values) => {
    preset.value = values || {}
    onto.value = null
    intoRail.value = false
    showCreate.value = true
  }

  /**
   * A new record that hangs off the one open, from the rail on its hero. The
   * only place in the product that knows which record a new one belongs to; the
   * parent goes in as a preset, which the person can still change.
   */
  const addChild = async ({ screen, field, value }) => {
    if (!screen || !field || !value) return
    preset.value = { [field]: value }
    intoRail.value = true
    onto.value =
      screen === spec.value?.screen ? null : await workspace.screenSpec(spaceCode, screen)
    showCreate.value = true
  }

  /**
   * A record that was just made is a record you want to be in — so the dialog
   * closes onto it rather than onto the list.
   *
   * Unless it was made from a record's own rail, and then the opposite: you
   * were reading a job and you added a variation to it.
   */
  const created = async (name) => {
    const fromRail = intoRail.value
    intoRail.value = false
    onto.value = null
    await reloadList()
    if (fromRail) {
      childRevision.value += 1
      return
    }
    if (name) router.push({ query: withAt(route.query, KIND.RECORD, name) })
  }

  return {
    showCreate, preset, childRevision, createSpec, createScreen,
    create, newWith, addChild, created,
  }
}
