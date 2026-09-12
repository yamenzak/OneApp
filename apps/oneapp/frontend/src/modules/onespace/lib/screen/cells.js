import { formatNumber, plainText } from '@/modules/onespace/lib/screen/format'
import { date, moment } from '@/shared/lib/runtime/format'

/**
 * What one cell's value *says*, as text.
 *
 * Lifted out of `FieldCell` when a second surface needed the same answer: a
 * gallery card draws its fields as pills over a photograph, where the cell's
 * own markup belongs to a light surface and the text does not. Two switches
 * over the same fieldtypes would be two answers to "what does a Duration look
 * like", and the second one always drifts.
 *
 * `formats` is the site's number settings, passed in rather than imported.
 * `link` is the row's already-resolved record for a Link column.
 */
export function cellText(column, value, formats = {}, link = null) {
  if (value === null || value === undefined || value === '') return '—'

  switch (column.cell) {
    case 'tags':
      // `_user_tags` is comma-joined by Frappe, with a leading comma left
      // behind on the first one by some versions.
      return tagList(value).join(', ')
    case 'link':
      return plainText(link?.label) || String(link?.value || value)
    case 'date':
      return date(value)
    case 'datetime':
      return moment(value)
    case 'percent':
      return `${formatNumber(value, column, formats)}%`
    case 'number':
    case 'currency':
      return formatNumber(value, column, formats)
    case 'duration':
      return humanDuration(Number(value) || 0, column)
    case 'check':
      return value ? 'Yes' : 'No'
    case 'html':
      // The list is not the place to render markup: a cell is one line, and
      // stripping is honest where interpreting would be a security decision.
      return plainText(value) || '—'
    default:
      return String(value)
  }
}

/**
 * A Duration, in the parts the docfield says are worth reading: `hide_days`
 * folds days into hours, `hide_seconds` drops the tail.
 */
export function humanDuration(seconds, column) {
  if (!seconds) return '—'
  const days = column.hide_days ? 0 : Math.floor(seconds / 86400)
  const hours = Math.floor((seconds - days * 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return (
    [
      days && `${days}d`,
      hours && `${hours}h`,
      minutes && `${minutes}m`,
      !column.hide_seconds && rest && `${rest}s`,
    ]
      .filter(Boolean)
      .join(' ') || (column.hide_seconds ? '0m' : `${seconds}s`)
  )
}

/**
 * `_user_tags` as a list. Frappe stores a record's tags as one comma-joined
 * string on the row, which is what makes a tag filterable with the same
 * machinery as any other column.
 */
export function tagList(value) {
  return String(value || '')
    .split(',')
    .map((one) => one.trim())
    .filter(Boolean)
}
