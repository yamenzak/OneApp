/**
 * The model catalogue, from the operator's side.
 *
 * Everything here is read through endpoints rather than through the doctype
 * resource, because the interesting part of a model is its rate rows and those
 * come back as a child table the list API will not join.
 *
 * There is deliberately no write path for prices. They are synced from the
 * provider and overwritten on the next run, so a control that edited them would
 * be a control that silently stops working.
 */

import { callMethod } from './resource'

// Method names are spelled out rather than built from a template. A name that
// only exists as a fragment cannot be grepped for, and `tests/test_no_desk.py`
// proves an operator surface exists by looking for exactly these strings.
const read = (method, params = {}) =>
  callMethod(`oneapp_control.api.${method}`, params, { silent: true, method: 'GET' })

export const ai = {
  settings: () => read('admin.ai_settings'),
  models: (params) => read('admin.ai_models', params),
  features: () => read('admin.ai_features'),
  usage: (params) => read('admin.ai_usage', params),

  sync: () =>
    callMethod('oneapp_control.api.admin.sync_ai_models', {}, {
      successMessage: 'Catalogue refreshed',
    }),

  updateModel: (model, values) =>
    callMethod('oneapp_control.api.admin.update_ai_model', { model, values }, {
      successMessage: 'Saved',
    }),

  updateFeature: (feature, values) =>
    callMethod('oneapp_control.api.admin.update_ai_feature', { feature, values }, {
      successMessage: 'Saved',
    }),

  setMarkup: (markup) =>
    callMethod('oneapp_control.api.admin.set_ai_markup', { markup }, {
      successMessage: 'Markup saved',
    }),

  reconcile: () =>
    callMethod('oneapp_control.api.admin.reconcile_ai_usage', {}, {
      successMessage: 'Compared against the gateway log',
    }),
}

/**
 * A model's rates, as one readable line per rate.
 *
 * Units differ by model — tokens, tiles, diffusion steps, audio minutes — so
 * this renders whatever the row says rather than assuming a shape. A table with
 * "input" and "output" columns could not show an image model at all.
 */
export function rateLines(model) {
  return (model.prices || [])
    .filter((p) => p.tier === 'Standard')
    .map((p) => {
      const per = p.per_units > 1 ? `${p.per_units.toLocaleString()} ` : ''
      const unit = `${per}${p.unit.toLowerCase()}${p.per_units > 1 ? 's' : ''}`
      const window = p.effective_from
        ? ` from ${p.effective_from}`
        : p.effective_to
          ? ` until ${p.effective_to}`
          : ''
      return `${p.kind} ${p.modality.toLowerCase()}: $${p.cost_usd} / ${unit}${window}`
    })
}

export const STATUS_THEME = {
  Available: 'green',
  Preview: 'blue',
  'Needs Review': 'amber',
  Deprecated: 'orange',
  Retired: 'gray',
}
