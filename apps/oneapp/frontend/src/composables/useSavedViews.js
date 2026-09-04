import { computed } from 'vue'

import { workspace } from '../lib/workspace'

/**
 * A screen is a named layout — filters, sort and columns saved together.
 *
 * Which is the shape Frappe's own `List Filter` doctype settles on. Which one
 * is open lives in the URL, so a screen is a link somebody can send.
 *
 * `payload` and `reload` are thunks: the host builds its request and reloads
 * its spec below this call, and every write here needs whichever is current at
 * the moment the button is pressed rather than at setup.
 */
export function useSavedViews({ spaceCode, spec, route, router, saving, dirty, payload, reload }) {
  const layout = computed(() => route.query.layout || '')

  const openLayout = (name) => {
    router.push({ query: { ...route.query, layout: name || undefined } })
  }

  // Every write goes through here, so the spec is re-read once and the Save
  // button is busy for exactly as long as the write takes.
  const withView = async (work) => {
    saving.value = true
    try {
      const result = await work()
      await reload(result?.layout)
      return result
    } finally {
      saving.value = false
    }
  }

  // Saved under a name, and opened straight away: the point of naming it is to
  // be in it.
  const saveAs = ({ label, icon, shared }) =>
    withView(async () => {
      const result = await workspace.saveLayout(spaceCode, spec.value.screen, {
        ...payload(),
        label,
        icon,
        shared,
      })
      dirty.value = false
      if (result?.layout) openLayout(result.layout)
      return result
    })

  // Every one of these names the view it acts on rather than assuming the one
  // on screen: the menu manages all of them, so "rename" can mean a view this
  // person is not looking at.
  //
  // What is on screen goes with a write only when it is meant to. Renaming the
  // view you are looking at carries it, because the alternative is a rename
  // that silently discards an unsaved change; renaming some *other* view must
  // not, because that would put this screen's filters into a view nobody was
  // editing. Saving into a view carries it either way — that is what saving
  // into it is.
  const intoLayout = (name, extra, carry = name === spec.value.layout) =>
    withView(() =>
      workspace.saveLayout(spaceCode, spec.value.screen, {
        ...(carry ? payload() : {}),
        layout: name,
        ...extra,
      }),
    )

  const renameLayout = ({ layout: name, label, icon, shared }) =>
    intoLayout(name, { label, icon, shared })

  const shareLayout = ({ layout: name, shared }) => intoLayout(name, { shared })

  // The other half of Save: put what is on screen into a view that already
  // exists rather than into a new one. Only offered for a view you may write.
  const saveIntoLayout = async (name) => {
    await intoLayout(name, {}, true)
    dirty.value = false
    if (name !== spec.value.layout) openLayout(name)
  }

  const defaultLayout = (name) =>
    withView(() => workspace.defaultLayout(spaceCode, spec.value.screen, name))

  // Deleting and hiding both go back to the screen's own declaration when they
  // acted on the view that is open — staying in a view you just removed from
  // your menu reads as a button that did nothing — and reload otherwise.
  const after = async (name) => {
    if (layout.value === name) openLayout('')
    else await reload()
  }

  const write = async (work, name) => {
    saving.value = true
    try {
      await work()
    } finally {
      saving.value = false
    }
    await after(name)
  }

  const deleteLayout = (name) =>
    write(() => workspace.deleteLayout(spaceCode, spec.value.screen, name), name)

  // Hiding is not deleting, and the difference matters: the view stays where it
  // is for everybody else.
  const hideLayout = (name) =>
    write(() => workspace.hideLayout(spaceCode, spec.value.screen, name), name)

  const showLayouts = () =>
    withView(() => workspace.showLayouts(spaceCode, spec.value.screen))

  return {
    layout, openLayout, saveAs, renameLayout, shareLayout, saveIntoLayout,
    defaultLayout, deleteLayout, hideLayout, showLayouts,
  }
}
