/**
 * Dropping files on something. One implementation, five call sites.
 *
 * Drag-and-drop landed on nine surfaces and each of the five that were about
 * *files* had written its own: its own `dragenter`/`dragover`/`dragleave`,
 * its own counter for the fact that both fire for every child the pointer
 * crosses, its own hover treatment — so a drop target in the Drive and a drop
 * target in the picker did not look alike — and its own answer to a folder
 * being dropped, which arrives as a zero-byte `File` with no type and
 * uploads as an empty file named after the folder.
 *
 * The other four are reordering — a board column, a print format's zone, the
 * column picker, a sheet's tabs — and keep their own, because a row dragged
 * within a list is a different gesture that happens to share three events.
 *
 * Three things it does that a hand-rolled handler mostly did not:
 *
 *   * **The treatment is §B4's `DROP`**, so every drop target in the product
 *     lights the same way.
 *   * **It ignores a drag that is not carrying files.** A row being dragged
 *     over a folder is not an upload, and a target that lights for it is a
 *     target that lies.
 *   * **It refuses what is over the ceiling before a byte is sent**, with the
 *     sentence §D3 put under the control, so the rejection reads the same
 *     whether a person dropped the file or chose it.
 *
 * Used as `v-drop-files="onFiles"` or `v-drop-files="{ onFiles, disabled }"`.
 *
 * `docs/UNIFICATION.md` §D3.
 */
import { DROP } from '@/shared/lib/rowstate'
import { withinCeiling } from '@/shared/lib/files/limits'
import { notifyError } from '@/shared/lib/runtime/notify'

const LIT = DROP.split(' ')

/** What the binding said, in one shape. */
function read(value) {
  if (typeof value === 'function') return { onFiles: value, disabled: false }
  return { onFiles: value?.onFiles, disabled: !!value?.disabled }
}

//: A directory arrives as a zero-byte `File` with no type.
const real = (file) => !!file && (!!file.size || !!file.type)

const carryingFiles = (event) => !!event.dataTransfer?.types?.includes('Files')

export const dropFiles = {
  mounted(el, binding) {
    // Counted rather than toggled: dragging over a child fires `dragleave` on
    // the parent, so a boolean flickers the whole time the pointer is inside.
    let depth = 0

    const dim = () => {
      depth = 0
      el.classList.remove(...LIT)
    }

    const handlers = {
      dragenter(event) {
        if (read(el.__dropFiles).disabled || !carryingFiles(event)) return
        event.preventDefault()
        depth += 1
        el.classList.add(...LIT)
      },
      dragover(event) {
        if (read(el.__dropFiles).disabled || !carryingFiles(event)) return
        // Without this the browser navigates to the file instead.
        event.preventDefault()
      },
      dragleave() {
        depth = Math.max(0, depth - 1)
        if (!depth) el.classList.remove(...LIT)
      },
      drop(event) {
        const { onFiles, disabled } = read(el.__dropFiles)
        if (disabled || !carryingFiles(event)) return
        event.preventDefault()
        dim()

        const { good, why } = withinCeiling(
          Array.from(event.dataTransfer?.files || []).filter(real),
        )
        if (why) notifyError(why)
        if (good.length) onFiles?.(good)
      },
    }

    el.__dropFiles = binding.value
    el.__dropFilesOff = () => {
      for (const [name, fn] of Object.entries(handlers)) el.removeEventListener(name, fn)
    }
    for (const [name, fn] of Object.entries(handlers)) el.addEventListener(name, fn)
  },

  // Re-read rather than re-bound: the handlers close over `el.__dropFiles`,
  // so a target that becomes disabled mid-drag stops responding without the
  // listeners being torn down under the pointer.
  updated(el, binding) {
    el.__dropFiles = binding.value
  },

  unmounted(el) {
    el.__dropFilesOff?.()
    delete el.__dropFiles
    delete el.__dropFilesOff
  },
}

export default dropFiles
