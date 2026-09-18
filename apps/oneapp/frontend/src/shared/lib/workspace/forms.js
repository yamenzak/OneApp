/** Forms — `oneapp/oneforms/service.py`. */

import { callMethod } from '@/shared/lib/runtime/resource'

export const forms = {
  /** This workspace's forms, and what it may make one over. */
  formsMine: () =>
    callMethod('oneapp.oneforms.service.forms', {}, { silent: true, method: 'GET' }),

  /**
   * A new form over one of the offerable doctypes.
   *
   * Not silent, and none of the four below are: a refusal here is the rule the
   * whole module hangs on — "that is not something you can make a form over" —
   * and it is a sentence the person pressing the button needs to read.
   */
  formMake: (doctype, title) =>
    callMethod('oneapp.oneforms.service.make', { doctype, title }),

  formRename: (name, title) =>
    callMethod('oneapp.oneforms.service.rename', { name, title }),

  formPublish: (name, live) =>
    callMethod('oneapp.oneforms.service.publish', { name, live: live ? 1 : 0 }),

  formForget: (name) =>
    callMethod('oneapp.oneforms.service.forget', { name }),

  /** One form: its settings, the fields on it, and what else it could carry. */
  formRead: (name) =>
    callMethod('oneapp.oneforms.service.read', { name }, { silent: true, method: 'GET' }),

  /**
   * The fields on a form, in the order they were dragged into.
   *
   * Replaced rather than merged, which is what a drag-and-drop builder means:
   * the browser holds the whole list and reconciling two orderings would be
   * inventing a conflict nobody has.
   */
  formLayout: (name, fields) =>
    callMethod('oneapp.oneforms.service.layout', {
      name, fields: JSON.stringify(fields),
    }),

  /** Who has been invited to this form, and whether they used it. */
  formInvitations: (name) =>
    callMethod('oneapp.oneforms.invite.invitations', { name },
      { silent: true, method: 'GET' }),

  /**
   * One invitation: a key, what it pre-fills, and what it may touch.
   *
   * Mailed where an address was given and made either way — sending the link
   * by hand is an ordinary thing, and a maker that insisted on an address
   * would be a maker with a second path around it.
   */
  formInvite: (name, to, values, about) =>
    callMethod('oneapp.oneforms.invite.invite', {
      name, to, about, values: JSON.stringify(values || {}),
    }),

  /** Take one link back. The page stops answering for whoever holds it. */
  formUninvite: (request) =>
    callMethod('oneapp.oneforms.invite.uninvite', { request }),

  /** Its switches — who may reach it and what it says. */
  formSettings: (name, values) =>
    callMethod('oneapp.oneforms.service.settings', {
      name, values: JSON.stringify(values),
    }),

  /**
   * The stylesheet on the page strangers open.
   *
   * Its own door rather than a key in `formSettings`, because it is code on a
   * public page: the server refuses an `@import`, a `url()` to another site
   * and anything that closes the element, and each refusal is a sentence the
   * person who wrote the rule needs to read.
   */
  formStyle: (name, css) =>
    callMethod('oneapp.oneforms.service.style', { name, css }),
}
