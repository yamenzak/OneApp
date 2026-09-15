/**
 * Who a record is, as the four things every surface draws it with.
 *
 * `{ value, label, id, image }` — the shape `RecordChip` takes, which is the
 * shape the server's own link options come back in. The reading is one line of
 * arithmetic and it was written twice the moment a second surface needed it:
 * the record's own view drew this for the trail, and the window's title bar
 * needed exactly the same thing from outside the component that computed it.
 *
 * The one rule worth naming is `id`. A record whose title *is* its name —
 * `ACC-SINV-2026-00005`, most submittables — has nothing to put underneath,
 * and drawing the name twice in two sizes reads as a bug rather than as
 * detail. So it is empty where the two agree.
 */
export function identityOf(record, spec) {
  const field = spec?.title_field
  const label = (field && record?.[field]) || record?.name
  return {
    value: record?.name || '',
    label: String(label || ''),
    id: label === record?.name ? '' : record?.name || '',
    image: (spec?.image_field ? record?.[spec.image_field] : '') || '',
  }
}
