/**
 * Making a record from a screen.
 *
 * Three doors lead here and they want different things afterwards. The header's
 * New makes one of this screen's records and lands you in it. A board column's
 * New does the same with the column's own status already filled in, because
 * making somebody choose the status they just pressed is the kind of small
 * stupidity that makes a board not worth using. And the plus on a showcase's
 * rail makes something that hangs off the record being read — possibly of a
 * different screen entirely — and must leave you where you were.
 *
 * Which is why `intoRail` is a flag rather than something inferred from the
 * preset: a board's New sets a preset too, and the two want opposite endings.
 */
import { computed, ref } from 'vue'

import { workspace } from '../lib/workspace'

export function useCreating({ spaceCode, spec, route, router, reloadList }) {
  const showCreate = ref(false)
  // What the dialog opens with already filled in. Empty for the header's New.
  const preset = ref({})
  // Whether the dialog that is open was opened by the rail's plus.
  const intoRail = ref(false)
  // What the showcase's rail has been told to re-read. Bumped rather than
  // reloaded directly: the rail is inside two components and a number
  // travelling down as a prop is less machinery than a handle travelling up.
  const childRevision = ref(0)

  /**
   * Which screen the dialog is filling in, and how it describes itself.
   *
   * Nearly always this one. The exception is the rail: what hangs off a record
   * may be a different screen — a job's variations happen to be projects, but a
   * property's inspections would not be — and a dialog drawn from this screen's
   * spec would ask for the wrong fields entirely.
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
   * A new record that hangs off the one open, from the rail on its hero.
   *
   * The only place in the product that knows which record a new one belongs to,
   * which is the whole reason it exists: the alternative is creating it from
   * its own list and remembering to set the parent by hand.
   *
   * The parent goes in as a preset — an ordinary value in an ordinary control,
   * which the person can still change before saving.
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
   * closes onto it rather than onto the list, which would leave the person
   * hunting for the row they created.
   *
   * Unless it was made from a record's own rail, and then the opposite: you
   * were reading a job and you added a variation to it, so the job is where you
   * still want to be. The rail re-reads itself and the new one is in it.
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
    if (name) router.push({ query: { ...route.query, record: name } })
  }

  return {
    showCreate, preset, childRevision, createSpec, createScreen,
    create, newWith, addChild, created,
  }
}
