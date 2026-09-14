/**
 * What the reader has open, for the assistant to be scoped to.
 *
 * Its own module, not `nav.js`, because two things need it and one of them is
 * `apps.js` — which `nav.js` imports, so asking `nav.js` for it would be a
 * cycle. Nothing here is a destination; it is the one question every surface
 * asks about the address bar.
 */
import { KIND, atOf } from '@/shared/lib/url/at'
import { openContext as declaredContext } from '@/shared/lib/ai/context'
import { session } from '@/modules/onespace/lib/shell/session'

export function openContext(route, spaces = session.spaces) {
  // What a page said about itself wins over what a route can be read to mean —
  // see `shared/lib/ai/context.js`. A document knows its own title and a route
  // to `/one/docs/<id>` does not, which is why the panel beside one used to
  // offer to talk about the workspace.
  const said = declaredContext(route, null)
  if (said) return said

  return screenContext(route, spaces)
}


/** Context from the address alone, which is every record screen in the product. */
function screenContext(route, spaces) {
  const code = route?.params?.spaceCode
  const screen = route?.query?.screen
  if (!code || !screen) return null

  const space = spaces.find((one) => one.space_code === code)
  const found = (space?.screens || []).find((one) => one.screen === screen)
  if (!found) return null

  const record = atOf(route.query, KIND.RECORD)
  return {
    space: code,
    screen,
    ...(record ? { docname: record } : {}),
    // Said to the reader, not to the model: the panel puts it under its own
    // title so what the answers will be about is legible before the first
    // question rather than inferred from the first answer.
    label: record ? `${found.label} · ${record}` : found.label,
  }
}
