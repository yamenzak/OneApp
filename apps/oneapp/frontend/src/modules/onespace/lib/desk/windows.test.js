// What is open on the desk, and what one press of a tile means.
//
// The whole of this module is a list and an order, so the cases are about the
// order: that raising does not open, that opening twice does not open twice,
// and that a folded window is still there. `docs/UNIFICATION.md` F3 — the
// press is the guard everything else goes through, so it gets the most of them.

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  FLOOR, LAYER, byArrival, clear, close, closeAll, desk, fold, frontOf, inFront,
  mountLayer, onDesk, open, press, raise, shown, visible, zOf,
} from './windows'

beforeEach(() => clear())

describe('opening', () => {
  it('puts a window on the desk and in front', () => {
    open('mail')
    expect(onDesk('mail')).toBe(true)
    expect(shown('mail')).toBe(true)
    expect(inFront('mail')).toBe(true)
  })

  it('does not open the same window twice', () => {
    // The assistant's shortcut, its dock tile and a record's own control all
    // call this, and two assistants is two conversations.
    open('assistant')
    open('assistant')
    expect(desk.open).toHaveLength(1)
  })

  it('brings a window that was behind back to the front', () => {
    open('mail')
    open('files')
    expect(inFront('mail')).toBe(false)
    open('mail')
    expect(inFront('mail')).toBe(true)
    expect(desk.open).toHaveLength(2)
  })

  it('unfolds one that was folded', () => {
    open('mail')
    fold('mail')
    expect(shown('mail')).toBe(false)
    open('mail')
    expect(shown('mail')).toBe(true)
  })
})

describe('the stack', () => {
  it('is the order of the list, so nothing is renumbered when one closes', () => {
    open('mail')
    open('files')
    open('assistant')
    expect(zOf('mail')).toBeLessThan(zOf('files'))
    expect(zOf('files')).toBeLessThan(zOf('assistant'))

    close('files')
    expect(zOf('mail')).toBe(FLOOR)
    expect(zOf('assistant')).toBe(FLOOR + 1)
  })

  it('answers the floor for a window nobody opened', () => {
    expect(zOf('nobody')).toBe(FLOOR)
  })

  it('will not raise a folded window', () => {
    // Raising something nobody can see is how a window comes to be open and
    // invisible with no way back to it.
    open('mail')
    open('files')
    fold('mail')
    raise('mail')
    expect(inFront('files')).toBe(true)
    expect(shown('mail')).toBe(false)
  })

  it('will not raise one that is not open', () => {
    open('mail')
    raise('files')
    expect(desk.open).toHaveLength(1)
    expect(inFront('mail')).toBe(true)
  })
})

describe('one press of a tile', () => {
  it('opens what was shut', () => {
    press('mail')
    expect(shown('mail')).toBe(true)
  })

  it('folds what is already in front', () => {
    // The only thing left to ask of a window you are looking at is to stop
    // looking at it.
    press('mail')
    press('mail')
    expect(onDesk('mail')).toBe(true)
    expect(shown('mail')).toBe(false)
  })

  it('raises what is open and behind, rather than folding it', () => {
    press('mail')
    press('files')
    press('mail')
    expect(shown('mail')).toBe(true)
    expect(inFront('mail')).toBe(true)
  })

  it('unfolds what was folded', () => {
    press('mail')
    press('mail')
    press('mail')
    expect(shown('mail')).toBe(true)
  })
})

describe('the layer every window is drawn in', () => {
  // The suite runs on `node`, where there is no document — which is also the
  // case this has to survive, because the module is imported before anything
  // is mounted. A minimal DOM is enough to say what the rule is.
  const document_ = () => {
    const body = { children: [], appendChild(el) {
      const at = body.children.indexOf(el)
      if (at !== -1) body.children.splice(at, 1)
      body.children.push(el)
    } }
    return {
      body,
      getElementById: (id) => body.children.find((one) => one.id === id) || null,
      createElement: () => ({ id: '', className: '', style: {} }),
    }
  }

  it('is one element, however many times it is asked for', () => {
    vi.stubGlobal('document', document_())
    mountLayer()
    mountLayer()
    open('mail')
    expect(document.body.children).toHaveLength(1)
    expect(document.body.children[0].id).toBe(LAYER)
    vi.unstubAllGlobals()
  })

  it('goes to the end of the body whenever a window opens', () => {
    // The whole of how this layers against a dialog. A dialog portals itself to
    // `body` at the same depth, so the tie is broken by document order: one
    // opened while the desk is sitting there covers it, and a window opened
    // from inside that dialog moves the desk back to the end and covers it in
    // turn. A Link peeked from a create dialog opening *behind* the dialog that
    // asked for it is the bug this is.
    const doc = document_()
    vi.stubGlobal('document', doc)
    mountLayer()
    const dialog = { id: 'a-dialog' }
    doc.body.appendChild(dialog)
    expect(doc.body.children[1]).toBe(dialog)

    open('record')
    expect(doc.body.children[1].id).toBe(LAYER)
    vi.unstubAllGlobals()
  })

  it('says nothing and throws nothing where there is no document', () => {
    vi.stubGlobal('document', undefined)
    expect(() => mountLayer()).not.toThrow()
    expect(() => open('mail')).not.toThrow()
    vi.unstubAllGlobals()
  })
})

describe('what the dock draws it from', () => {
  it('keeps the name and glyph it was opened with', () => {
    // A window no app tile stands for — a picture-in-picture list — has
    // nothing else to be drawn from, and a tile you have to press to find out
    // what it is is not a tile.
    open('pip', { label: 'People', icon: 'lucide-list' })
    expect(desk.open[0]).toMatchObject({ label: 'People', icon: 'lucide-list' })
  })

  it('does not blank them when it is raised', () => {
    open('pip', { label: 'People', icon: 'lucide-list' })
    open('mail')
    open('pip')
    expect(desk.open[desk.open.length - 1]).toMatchObject({ label: 'People' })
  })

  it('lets a second opening rename it', () => {
    // The same window, over a different screen: the list in it is the one
    // behind whatever record is open now.
    open('pip', { label: 'People' })
    open('pip', { label: 'Attendance' })
    expect(desk.open[0].label).toBe('Attendance')
  })
})

describe('closing', () => {
  it('takes it off the desk', () => {
    open('mail')
    close('mail')
    expect(onDesk('mail')).toBe(false)
  })

  it('is quiet about a window that was never open', () => {
    expect(() => close('nobody')).not.toThrow()
  })

  it('leaves nothing in front when the last one goes', () => {
    open('mail')
    close('mail')
    expect(inFront('mail')).toBe(false)
  })
})

describe('a family of windows sharing one corner', () => {
  // Several record previews are open at once — `composables/usePeek.js`. They
  // all remember the same box, so every one but the front is covered to the
  // pixel, and the host draws that one alone. The questions this answers are
  // which, and which of them anybody can actually see.
  const KIN = 'record:'
  const kin = (id) => open(id, { family: KIN })

  it('names the frontmost drawn one', () => {
    kin('record:clients/CL-0003')
    kin('record:projects/PR-0002')
    expect(frontOf(KIN)).toBe('record:projects/PR-0002')
  })

  it('looks past a folded one, because a folded window is not on screen', () => {
    kin('record:clients/CL-0003')
    kin('record:projects/PR-0002')
    fold('record:projects/PR-0002')
    expect(frontOf(KIN)).toBe('record:clients/CL-0003')
  })

  it('looks past anything that is not family', () => {
    // The assistant in front of a preview does not make the preview the one to
    // stop drawing: they are different sizes in different corners.
    kin('record:clients/CL-0003')
    open('assistant')
    expect(frontOf(KIN)).toBe('record:clients/CL-0003')
  })

  it('is empty where none of them is open', () => {
    open('assistant')
    expect(frontOf(KIN)).toBe('')
  })

  it('shuts all of them and leaves the rest', () => {
    open('assistant')
    kin('record:clients/CL-0003')
    kin('record:projects/PR-0002')
    closeAll(KIN)
    expect(desk.open.map((one) => one.id)).toEqual(['assistant'])
  })

  it('carries a face for the tile that draws it', () => {
    // Five previews are five records, and five copies of one glyph is a row
    // you have to press to read.
    open('record:clients/CL-0003', { label: 'zzMeridian Group', image: '/files/m.png', face: true })
    expect(desk.open[0]).toMatchObject({
      label: 'zzMeridian Group', image: '/files/m.png', face: true,
    })
  })

  it('still says face for a record with no picture, which is its initials', () => {
    open('record:clients/CL-0003', { label: 'zzMeridian Group', face: true })
    expect(desk.open[0]).toMatchObject({ label: 'zzMeridian Group', image: '', face: true })
  })

  it('leaves a window that is not a record on its glyph', () => {
    open('pip', { label: 'People', icon: 'lucide-list' })
    expect(desk.open[0].face).toBe(false)
  })
})

describe('whether anybody can see it', () => {
  // `shown` says a window is not folded, which was the whole question while
  // every window had a corner to itself. Two previews unfolded is one of them
  // visible and one behind it to the pixel, and a dock that lit both was
  // saying two windows were on screen when one had nothing to see.
  const KIN = 'record:'
  const kin = (id) => open(id, { family: KIN })

  it('is only the front one of a family', () => {
    kin('record:clients/CL-0003')
    kin('record:projects/PR-0002')
    expect(shown('record:clients/CL-0003')).toBe(true)
    expect(visible('record:clients/CL-0003')).toBe(false)
    expect(visible('record:projects/PR-0002')).toBe(true)
  })

  it('moves to whichever of them was raised', () => {
    kin('record:clients/CL-0003')
    kin('record:projects/PR-0002')
    press('record:clients/CL-0003')
    expect(visible('record:clients/CL-0003')).toBe(true)
    expect(visible('record:projects/PR-0002')).toBe(false)
  })

  it('is nothing for a folded one, family or not', () => {
    kin('record:clients/CL-0003')
    open('assistant')
    fold('record:clients/CL-0003')
    fold('assistant')
    expect(visible('record:clients/CL-0003')).toBe(false)
    expect(visible('assistant')).toBe(false)
  })

  it('is the same as shown for a window with a corner to itself', () => {
    // The assistant behind a preview is still a window you can see: they are
    // different sizes in different places.
    open('assistant')
    kin('record:clients/CL-0003')
    expect(visible('assistant')).toBe(true)
  })

  it('is nothing for a window that was never opened', () => {
    expect(visible('nobody')).toBe(false)
  })
})

describe('the order the dock draws them in', () => {
  // Not the stack's. `desk.open` is which covers which, so raising a window
  // moves it — and a dock read straight off it rearranged itself under the
  // pointer that had just pressed one of its tiles.
  it('is the order they arrived, whatever the stack has done since', () => {
    open('pip')
    open('record:clients/CL-0003')
    open('record:projects/PR-0002')
    open('pip')
    open('record:clients/CL-0003')
    expect(byArrival(desk.open).map((one) => one.id)).toEqual([
      'pip', 'record:clients/CL-0003', 'record:projects/PR-0002',
    ])
  })

  it('gives a window back its place when it is folded and raised', () => {
    open('record:clients/CL-0003')
    open('record:projects/PR-0002')
    fold('record:clients/CL-0003')
    open('record:clients/CL-0003')
    expect(byArrival(desk.open).map((one) => one.id)).toEqual([
      'record:clients/CL-0003', 'record:projects/PR-0002',
    ])
  })

  it('does not renumber a window that closes and comes back', () => {
    // It is a new window then, and a new window goes on the end. Anything else
    // means a tile appearing in the middle of a row somebody was reading.
    open('one')
    open('two')
    close('one')
    open('one')
    expect(byArrival(desk.open).map((one) => one.id)).toEqual(['two', 'one'])
  })
})
