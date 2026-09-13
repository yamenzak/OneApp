/**
 * What to offer somebody who has opened the assistant and not yet typed.
 *
 * An empty chat is the one screen where a person has to invent the question,
 * and inventing it is the step most of them do not take. Four openers, chosen
 * by what is actually open, turn that into a press — and they are the clearest
 * possible statement of what the panel can see, which is a thing a sentence
 * under a face was never going to say convincingly.
 *
 * They are questions rather than commands, because the answer arrives as text
 * in a conversation. "Summarise this" and "What does it say about payment
 * terms?" both work; "Rewrite the second paragraph" does not, and offering it
 * would teach the wrong thing about a panel that cannot type into a document.
 * What rewrites a document is the verb menu in its own toolbar — `AiMenu`,
 * `shared/lib/ai/verbs.js` — and the split is deliberate: a transform belongs
 * where the selection is, a question belongs here.
 *
 * Written as functions returning literals rather than as a map at module scope,
 * for the reason every other list of `__()` in this app is: a map built at
 * module scope calls the translator before the catalogue has loaded, and the
 * extractor needs each string as a literal.
 */

import { __ } from '@/shared/lib/runtime/translate'

/** A workbook: the questions are about the numbers, not about the prose. */
const workbookOpeners = () => [
  __('What does this workbook work out?'),
  __('Are there any figures that look wrong?'),
  __('Which cells feed the total?'),
  __('Summarise what is in each tab.'),
]

/** A document: what it says, and what it commits anybody to. */
const documentOpeners = () => [
  __('Summarise this in five lines.'),
  __('What does it commit us to?'),
  __('What is missing that a reader would ask for?'),
  __('Which records is this about?'),
]

/** Anything else with a file behind it — a PDF, a drawing, a recording. */
const fileOpeners = () => [
  __('What is this file for?'),
  __('Where else is it referenced?'),
  __('Who has access to it?'),
  __('What changed most recently around it?'),
]

/** One record on a screen. */
const recordOpeners = () => [
  __('Summarise this one.'),
  __('How does it compare with the last few?'),
  __('What is outstanding on it?'),
  __('Which files are filed against it?'),
]

/** A screen with no record chosen. */
const screenOpeners = () => [
  __('What is on this screen right now?'),
  __('What needs attention first?'),
  __('How many are there by status?'),
  __('What changed this week?'),
]

/** The rail: nothing open, so the questions are about the whole workspace. */
const workspaceOpeners = () => [
  __('What should I look at first today?'),
  __('What is waiting on me?'),
  __('Find a document about…'),
  __('What changed in the last week?'),
]

/**
 * The four to offer for one context.
 *
 * `kind` is the file's own `custom_kind` where there is a file — the same
 * closed set `onestorage/kinds.py` holds — so a workbook and a scope of works
 * are asked about differently without either page having to say how.
 */
/**
 * A passage is highlighted, so every question is about that and not the file.
 *
 * These are the four people actually want on a paragraph, and three of them
 * produce something to put back — which is the pairing that makes the Insert
 * button worth having: highlight, ask, insert over what you highlighted.
 */
const selectionOpeners = () => [
  __('Summarise this passage.'),
  __('Say this more plainly.'),
  __('What does this commit us to?'),
  __('Shorten this by half.'),
]

/**
 * Cells are highlighted, so the questions are about arithmetic and not prose.
 *
 * "Shorten this by half" is nonsense on a range, and "which cells feed this?"
 * is the question a person actually has in front of a total they did not
 * write — which is exactly what the digest carries the formulas for.
 */
const rangeOpeners = () => [
  __('What do these cells work out?'),
  __('Which cells feed this?'),
  __('Is anything here wrong or inconsistent?'),
  __('Explain this formula.'),
]

export function openersFor(on) {
  if (on?.selection) {
    return on.kind === 'Sheet' ? rangeOpeners() : selectionOpeners()
  }
  if (on?.file) {
    if (on.kind === 'Sheet') return workbookOpeners()
    if (on.kind === 'Doc' || on.kind === 'Document') return documentOpeners()
    return fileOpeners()
  }
  if (on?.space && on?.docname) return recordOpeners()
  if (on?.space) return screenOpeners()
  return workspaceOpeners()
}
