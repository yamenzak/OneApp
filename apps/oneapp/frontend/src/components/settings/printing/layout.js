/**
 * A print format's layout, as the builder holds it and Frappe renders it.
 *
 * The shape is not ours. `format_data` on a Frappe beta Print Format is
 *
 *     {sections: [{columns: [{fields: [...], width}], justify, gap}],
 *      header: {columns: [...]}, footer: {columns: [...]}}
 *
 * and `PrintFormatGenerator` walks exactly that. Building over Frappe's own
 * contract is why a format drawn here prints the same wherever it is opened.
 * Everything here is a helper *around* that shape, never a translation of it.
 */

/**
 * A client-side identity for a thing on the canvas: Vue needs a stable `:key`
 * and the layout has no id of its own. Stripped on the way out.
 */
let counter = 0
export const identify = (thing) => {
  thing._id = `e${(counter += 1)}`
  return thing
}

/** An empty layout: one section, one column, nothing in it. */
export const emptyLayout = () => ({
  sections: [emptySection()],
  header: { columns: [emptyColumn()] },
  footer: { columns: [emptyColumn()] },
})

export const emptySection = () => ({ columns: [emptyColumn()], gap: 20 })

export const emptyColumn = () => ({ fields: [], width: 1 })

/**
 * A layout from the server, given ids and its gaps filled in. A format saved
 * before a key existed does not carry it, and tolerating that is easier done
 * once here than in every `v-for` that touches it.
 */
export const adopt = (raw) => {
  const found = raw && typeof raw === 'object' ? raw : {}
  const zone = (one) => ({
    ...one,
    columns: ((one && one.columns) || []).map((column) => ({
      width: 1,
      ...column,
      fields: ((column && column.fields) || []).map((field) => identify({ ...field })),
    })),
  })

  const sections = (found.sections || []).map((one) => ({ gap: 20, ...zone(one) }))
  return {
    sections: sections.length ? sections : [emptySection()],
    header: zone(found.header || { columns: [emptyColumn()] }),
    footer: zone(found.footer || { columns: [emptyColumn()] }),
  }
}

/** The same layout with the canvas's own bookkeeping taken back off. */
export const stripped = (layout) => {
  const zone = (one) => ({
    ...one,
    columns: (one.columns || []).map((column) => ({
      ...column,
      fields: (column.fields || []).map((field) => {
        const kept = { ...field }
        delete kept._id
        return kept
      }),
    })),
  })
  return {
    sections: (layout.sections || []).map(zone),
    header: zone(layout.header),
    footer: zone(layout.footer),
  }
}

/**
 * What one palette entry becomes when it lands on a column. The elements carry
 * their own defaults because an element with none renders as nothing, which
 * reads as a broken builder.
 */
export const dropped = (entry) => {
  if (entry.kind === 'element') {
    const made = { fieldtype: entry.fieldtype }
    if (entry.fieldtype === 'HTML') made.html = '<p>Your text, or {{ doc.name }}.</p>'
    if (entry.fieldtype === 'Spacer') made.height = 16
    if (entry.fieldtype === 'Image') made.align = 'left'
    if (entry.fieldtype === 'Barcode') made.align = 'left'
    return identify(made)
  }

  const made = {
    fieldname: entry.fieldname,
    fieldtype: entry.fieldtype,
    label: entry.label,
  }
  // A table with no columns prints an empty table, so it lands with the child's
  // first few already on.
  if (entry.kind === 'table') {
    made.table_columns = (entry.columns || []).slice(0, 5).map((one) => ({ ...one }))
  }
  return identify(made)
}

/** Where an element sits, as one value a drag can carry. */
export const address = (zone, section, column, index) =>
  JSON.stringify({ zone, section, column, index })

export const parse = (raw) => {
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

/** The columns of one zone, by the name the address uses. */
export const columnsOf = (layout, zone, section) =>
  zone === 'sections' ? layout.sections[section].columns : layout[zone].columns
