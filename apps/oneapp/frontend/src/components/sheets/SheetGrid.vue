<template>
  <!--
    The grid.

    One scroller owning both scrollbars, a header row that sticks to the top
    and a number column that sticks to the left. Rows are windowed: a sheet
    used down to row 800 is 800 × 26 cells, and twenty thousand divs is a
    browser that stops repainting while you type.

    not-a-tooltip: the `@mouseover` below drags a selection across the grid.
    It is a pointer gesture, not a hover card — there is nothing for
    frappe-ui's Tooltip to be here.

    Cells are divs, not inputs. There is exactly one editor and it is moved to
    whichever cell is being typed in — which is how every spreadsheet does it,
    and the difference between a grid that opens instantly and one that builds
    twenty thousand form controls first.
  -->
  <div
    ref="scroller"
    data-slot="sheet-grid"
    class="relative min-h-0 flex-1 overflow-auto outline-none"
    tabindex="0"
    role="grid"
    :aria-label="`${sheet.title.value || 'Sheet'}, ${sheet.active.value}`"
    :aria-rowcount="rows"
    :aria-colcount="columns.length"
    @scroll="onScroll"
    @keydown="onKey"
    @mouseup="dragging = false"
    @copy="onCopy"
    @paste="onPaste"
    @cut="onCut"
  >
    <div :style="{ width: `${ROW_HEAD + columns.length * COLUMN_WIDTH}px` }">
      <!-- Column headers -->
      <div role="row" aria-rowindex="1" class="sticky top-0 z-20 flex h-7 bg-surface-gray-2">
        <div
          role="columnheader"
          class="sticky left-0 z-30 shrink-0 border-b border-r border-outline-gray-2 bg-surface-gray-2"
          :style="{ width: `${ROW_HEAD}px` }"
        />
        <div
          v-for="column in columns"
          :key="column"
          role="columnheader"
          class="shrink-0 border-b border-r border-outline-gray-2 text-center text-p-xs leading-7 text-ink-gray-6"
          :class="inColumn(column) ? 'bg-surface-gray-4 text-ink-gray-8' : ''"
          :style="{ width: `${COLUMN_WIDTH}px` }"
        >
          {{ letters(column) }}
        </div>
      </div>

      <div :style="{ height: `${before}px` }" />

      <div
        v-for="row in visibleRows"
        :key="row"
        role="row"
        :aria-rowindex="row + 1"
        class="flex"
        :style="{ height: `${ROW_HEIGHT}px` }"
      >
        <div
          role="rowheader"
          class="sticky left-0 z-10 shrink-0 border-b border-r border-outline-gray-2 bg-surface-gray-2 text-center text-p-xs leading-7 text-ink-gray-6"
          :class="inRow(row) ? 'bg-surface-gray-4 text-ink-gray-8' : ''"
          :style="{ width: `${ROW_HEAD}px` }"
        >
          {{ row }}
        </div>
        <div
          v-for="column in columns"
          :key="column"
          class="relative shrink-0 truncate border-b border-r border-outline-gray-2 px-1.5 text-p-sm leading-7"
          :class="[
            selected(row, column) ? 'bg-surface-blue-1' : 'bg-surface-base',
            at(row, column) ? 'z-[1] ring-2 ring-outline-gray-4' : '',
          ]"
          :style="[{ width: `${COLUMN_WIDTH}px` }, styleOf(row, column)]"
          role="gridcell"
          :aria-colindex="column + 1"
          :aria-label="`${letters(column)}${row}`"
          @mousedown.prevent="onDown(row, column, $event)"
          @mouseover="onOver(row, column, $event)"
          @dblclick="startEditing()"
        >
          {{ shown(row, column) }}
        </div>
      </div>

      <div :style="{ height: `${after}px` }" />
    </div>

    <!--
      The one editor, parked over whichever cell is being typed in. Absolutely
      positioned inside the scroller's content, so it scrolls with the grid
      rather than floating over a cell it no longer covers.

      `v-show` and not `v-if`, which is the difference between a grid that
      keeps what you type and one that drops the first few characters of it.
      Typing a printable character starts an edit, and with `v-if` the input
      does not exist yet: focusing it has to wait for the next tick, and every
      keystroke that arrives before then lands on the grid, which is already in
      editing mode and ignores them. `=A1*A2` typed at speed became `1*A2`.
    -->
    <div
      ref="editorBox"
      v-show="sheet.editing.value"
      class="absolute z-30"
      :style="editorAt"
    >
      <TextInput
        v-model="sheet.draft.value"
        type="text"
        :aria-label="`Editing ${sheet.cursor.value}`"
        class="h-full w-full [&_input]:h-full [&_input]:bg-surface-base [&_input]:text-p-sm [&_input]:shadow-none [&_input]:ring-2 [&_input]:ring-outline-gray-4"
        @keydown.stop="onEditorKey"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { TextInput } from '@/ui'

import { columnLetters, format } from '../../lib/sheets/refs'
import { align, styleFor, text } from '../../lib/sheets/display'

// Fixed geometry, for now. Per-column widths are stored on `Sheet Tab` and
// dragging one is the next thing this grows; a uniform grid is what makes the
// windowing arithmetic a multiplication rather than a running total.
const ROW_HEIGHT = 28
const COLUMN_WIDTH = 104
const ROW_HEAD = 48

/** Rows drawn above and below the viewport, so a fast scroll is not blank. */
const OVERSCAN = 8

const props = defineProps({
  sheet: { type: Object, required: true },
  locale: { type: String, default: undefined },
})

const sheet = props.sheet
const scroller = ref(null)
const editorBox = ref(null)
const top = ref(0)
const height = ref(600)

const rows = computed(() => sheet.extent.value.rows)
const columns = computed(() =>
  Array.from({ length: sheet.extent.value.columns }, (unused, index) => index + 1))

const first = computed(() => Math.max(1, Math.floor(top.value / ROW_HEIGHT) + 1 - OVERSCAN))
const last = computed(() =>
  Math.min(rows.value, Math.ceil((top.value + height.value) / ROW_HEIGHT) + OVERSCAN))
// Not `window`: that is the browser global, and shadowing it here is how a
// mouseup listener ended up being registered on a computed ref.
const visibleRows = computed(() =>
  Array.from({ length: Math.max(0, last.value - first.value + 1) },
             (unused, index) => first.value + index))

const before = computed(() => (first.value - 1) * ROW_HEIGHT)
const after = computed(() => Math.max(0, (rows.value - last.value) * ROW_HEIGHT))

function onScroll(event) {
  top.value = event.target.scrollTop
  height.value = event.target.clientHeight
}

const letters = columnLetters

function cellAt(row, column) {
  sheet.version.value
  return sheet.book.value.get(sheet.active.value, format(row, column))
}

function shown(row, column) {
  return text(cellAt(row, column), props.locale)
}

function styleOf(row, column) {
  const cell = cellAt(row, column)
  return cell ? styleFor(cell) : { textAlign: align(null) }
}

function at(row, column) {
  return sheet.anchor.row === row && sheet.anchor.column === column
}

function selected(row, column) {
  const { top: t, left, bottom, right } = sheet.area.value
  return row >= t && row <= bottom && column >= left && column <= right
}

const inColumn = (column) =>
  column >= sheet.area.value.left && column <= sheet.area.value.right
const inRow = (row) => row >= sheet.area.value.top && row <= sheet.area.value.bottom

// --------------------------------------------------------------------------- //
// Pointer
// --------------------------------------------------------------------------- //

const dragging = ref(false)

function onDown(row, column, event) {
  commit()
  sheet.select(row, column, { extend: event.shiftKey })
  dragging.value = true
  scroller.value?.focus()
}

function onOver(row, column, event) {
  // `buttons` rather than our own flag alone: a mouseup outside the grid never
  // reaches us, and without this the selection follows the pointer afterwards.
  if (!dragging.value || !event.buttons) return
  sheet.select(row, column, { extend: true })
}

// --------------------------------------------------------------------------- //
// Keyboard
// --------------------------------------------------------------------------- //

const MOVES = {
  ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1],
}

function onKey(event) {
  if (sheet.editing.value) return

  const move = MOVES[event.key]
  if (move) {
    event.preventDefault()
    sheet.move(move[0], move[1], { extend: event.shiftKey })
    return keepVisible()
  }

  if (event.key === 'Tab') {
    event.preventDefault()
    sheet.move(0, event.shiftKey ? -1 : 1)
    return keepVisible()
  }

  if (event.key === 'Enter') {
    event.preventDefault()
    if (event.altKey) return startEditing()
    sheet.move(event.shiftKey ? -1 : 1, 0)
    return keepVisible()
  }

  if (event.key === 'F2') {
    event.preventDefault()
    return startEditing()
  }

  if (event.key === 'Escape') {
    sheet.select(sheet.anchor.row, sheet.anchor.column)
    return undefined
  }

  if ((event.key === 'Delete' || event.key === 'Backspace') && sheet.canWrite.value) {
    event.preventDefault()
    return sheet.clear()
  }

  // Any printable character starts an edit with that character in it, which is
  // the behaviour that makes a grid feel like a grid rather than a form.
  if (
    event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey
    && sheet.canWrite.value
  ) {
    event.preventDefault()
    return startEditing(event.key)
  }

  return undefined
}

/**
 * The editor's `<input>`.
 *
 * Found through the wrapper rather than through the component's own `$el`,
 * which for a multi-root component is whatever node happens to be first — a
 * text node, in this case, and `focus` is not a function on one of those.
 */
function inputEl() {
  return editorBox.value?.querySelector('input') || null
}

function startEditing(seed) {
  if (!sheet.canWrite.value) return
  const opening = seed === undefined ? sheet.formula.value : seed
  sheet.draft.value = opening
  sheet.editing.value = true

  // The DOM is written directly as well as through the model, and focus is
  // taken in this same tick. Waiting for Vue to patch the input would leave a
  // window in which the element still holds the previous text while somebody
  // is already typing into it — and the first `input` event would then
  // overwrite the seed character with whatever came next.
  const input = inputEl()
  if (!input) return

  // `v-show` writes `display: none` and un-writes it on Vue's next patch, and
  // a hidden element cannot take focus. So the display is set here too, in the
  // same tick — the patch that follows agrees with it, because `editing` is
  // already true. Without this the seed character lands and every character
  // after it is typed into a grid that thinks it is already editing.
  editorBox.value.style.display = ''
  input.value = opening
  input.focus()
  if (seed === undefined) input.select()
  else input.setSelectionRange(opening.length, opening.length)
}

function onEditorKey(event) {
  if (event.key === 'Escape') {
    sheet.editing.value = false
    scroller.value?.focus()
    return
  }
  if (event.key === 'Enter') {
    event.preventDefault()
    commit()
    sheet.move(event.shiftKey ? -1 : 1, 0)
    scroller.value?.focus()
    keepVisible()
    return
  }
  if (event.key === 'Tab') {
    event.preventDefault()
    commit()
    sheet.move(0, event.shiftKey ? -1 : 1)
    scroller.value?.focus()
    keepVisible()
  }
}

function commit() {
  if (!sheet.editing.value) return
  sheet.editing.value = false
  sheet.write([{ tab: sheet.active.value, ref: sheet.cursor.value, raw: sheet.draft.value }])
}

defineExpose({ commit, startEditing, focus: () => scroller.value?.focus() })

// --------------------------------------------------------------------------- //
// Clipboard
// --------------------------------------------------------------------------- //

function onCopy(event) {
  event.clipboardData?.setData('text/plain', sheet.selectionText())
  event.preventDefault()
}

function onCut(event) {
  onCopy(event)
  if (sheet.canWrite.value) sheet.clear()
}

function onPaste(event) {
  if (!sheet.canWrite.value) return
  const text_ = event.clipboardData?.getData('text/plain')
  if (!text_) return
  event.preventDefault()
  sheet.paste(text_)
}

// --------------------------------------------------------------------------- //
// Keeping the cursor on screen
// --------------------------------------------------------------------------- //

function keepVisible() {
  const box = scroller.value
  if (!box) return
  const cellTop = (sheet.anchor.row - 1) * ROW_HEIGHT
  const cellLeft = ROW_HEAD + (sheet.anchor.column - 1) * COLUMN_WIDTH
  // 28px of header to clear at the top, and the row-number column at the left.
  if (cellTop < box.scrollTop + ROW_HEIGHT) box.scrollTop = Math.max(0, cellTop - ROW_HEIGHT)
  else if (cellTop + ROW_HEIGHT > box.scrollTop + box.clientHeight) {
    box.scrollTop = cellTop + ROW_HEIGHT - box.clientHeight
  }
  if (cellLeft < box.scrollLeft + ROW_HEAD) box.scrollLeft = Math.max(0, cellLeft - ROW_HEAD)
  else if (cellLeft + COLUMN_WIDTH > box.scrollLeft + box.clientWidth) {
    box.scrollLeft = cellLeft + COLUMN_WIDTH - box.clientWidth
  }
}

const editorAt = computed(() => ({
  top: `${(sheet.anchor.row - 1) * ROW_HEIGHT + 28}px`,
  left: `${ROW_HEAD + (sheet.anchor.column - 1) * COLUMN_WIDTH}px`,
  width: `${COLUMN_WIDTH}px`,
  height: `${ROW_HEIGHT}px`,
}))

// Changing tab moves the cursor home, and the scroller has to follow or the
// new tab opens showing row 400 of a sheet with twelve rows in it.
watch(() => sheet.active.value, () => {
  if (scroller.value) {
    scroller.value.scrollTop = 0
    scroller.value.scrollLeft = 0
  }
  top.value = 0
})
</script>
