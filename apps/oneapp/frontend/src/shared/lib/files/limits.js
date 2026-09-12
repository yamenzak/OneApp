/**
 * How big a file may be, said before somebody spends a minute finding out.
 *
 * There was no size messaging anywhere near an upload control. The only
 * sentence in the SPA about a size was `FileSurface`'s "too big to show here",
 * which is about *reading* a file. A person picked a 40 MB video, watched it
 * travel, and was told at the end.
 *
 * The number comes from the server, because it is not the same on every site:
 * below `directUpload.THRESHOLD` a file is POSTed to Frappe and the
 * framework's `max_file_size` bounds it; above it the bytes go straight to R2
 * in parts and nothing in between reads the body. So on a site with a bucket
 * there is no per-file ceiling worth printing and this says nothing — the
 * thing that refuses a large file there is the quota, which has its own words
 * and its own number. `onestorage/limits.py` decides which case a site is in.
 *
 * `docs/UNIFICATION.md` §D3.
 */
import { limits } from '@/shared/lib/runtime/boot'
import { sizeText } from '@/shared/lib/files/size'
import { __ } from '@/shared/lib/runtime/translate'

/** Bytes, or 0 where there is no fixed per-file ceiling here. */
export const CEILING = Number(limits?.file) || 0

/**
 * The sentence that goes under an attach control, or '' when there is no
 * ceiling to state. One clause, because it sits beside the control rather
 * than instead of it.
 */
export function ceilingNote() {
  return CEILING ? __('Up to {0} each.', [sizeText(CEILING)]) : ''
}

/** Whether this one would be refused. */
export const oversize = (file) => !!CEILING && Number(file?.size || 0) > CEILING

/**
 * What of this may be sent, and why the rest may not.
 *
 * Checked here rather than left to the server, because the server's refusal
 * arrives after the bytes did. Returns the sentence rather than raising it: a
 * dialog wants it in its `ErrorMessage` and a drop target wants it in a toast,
 * and neither wants an exception.
 */
export function withinCeiling(files) {
  const list = Array.from(files || [])
  const good = list.filter((one) => !oversize(one))
  if (good.length === list.length) return { good, refused: [], why: '' }

  const refused = list.filter(oversize)
  return {
    good,
    refused,
    why:
      refused.length === 1
        ? __('{0} is {1}, and the largest that can go here is {2}.', [
          refused[0].name, sizeText(refused[0].size), sizeText(CEILING),
        ])
        : __('{0} files are larger than {1} and were not sent.', [
          refused.length, sizeText(CEILING),
        ]),
  }
}
