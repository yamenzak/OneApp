/**
 * Which engine a project may be written against.
 *
 * The other half of `oneapp/onecode/engines.py`, and the reason it is a second
 * list rather than a fetch: this is a picker in a dialog, and a picker that
 * waits on a round trip to know what it offers is a dialog that opens empty.
 * `tests/test_onecode.py` reads both back — the same arrangement the language
 * catalogue already has, and for the same reason. An engine offered here and
 * absent from the map is a project that saves and will not load.
 *
 * The version is shown beside the label because a person choosing between
 * Preact and Vue on a page they cannot rebuild wants to know which Vue. It is
 * the server's number; nothing here decides it.
 */
import { __ } from '@/shared/lib/runtime/translate'

export const ENGINES = [
  { value: 'preact', label: __('Preact'), version: '10.26.4',
    hint: __('Small, and JSX without a build step.') },
  { value: 'vue', label: __('Vue'), version: '3.5.13',
    hint: __('Components as template strings.') },
  { value: 'lit', label: __('Lit'), version: '3.2.1',
    hint: __('Web components, close to the platform.') },
  { value: 'alpine', label: __('Alpine'), version: '3.14.9',
    hint: __('Behaviour written into the markup.') },
  { value: 'none', label: __('None'), version: '',
    hint: __('Plain modules and the DOM.') },
]

/** What to call an engine a project already picked. */
export const labelOf = (engine) =>
  ENGINES.find((one) => one.value === engine)?.label || __('None')
