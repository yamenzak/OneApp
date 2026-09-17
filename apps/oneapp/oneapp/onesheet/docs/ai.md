# AI

## One feature, and it is unlike every other one in the product

| Key | Label | What it does |
| --- | --- | --- |
| `sheet.plan` | Working in a sheet | Turns an instruction into a short plan of changes. |

**The answer is a plan, not text**, and that follows directly from the module's
first decision: the browser evaluates formulas and the server stores what it
computed. A server that wrote `=SUM(D2:D20)` into a cell would be writing a
workbook whose stored `values` disagree with its `sheet`, and there is no
browser on that side to recompute it.

## The six operations

    tab      make or select a sheet
    set      a cell's contents
    format   how it is drawn
    width    a column's width
    freeze   the panes
    name     a named range

Validated here, applied in the browser through `setCell`, `applyToRange`,
`setColWidth`, `setFreeze` and `pushEditOp` — **the same calls the toolbar and
the header's context menu use**. So the history has it as ordinary edits, and a
colleague in the workbook watches it arrive.

## `format` is the one that had to be taught

It was in the vocabulary from the start and the prompt never asked for it,
which is why a model told to build a quote sheet built a grid of raw text:
money in `general`, headings indistinguishable from data, columns cut off at
their default width.

The vocabulary now runs to rules, wrapping and a font size, and the prompt says
what a readable sheet *is* — a bold heading row on a light ground with a rule
under it and frozen, currency where the numbers are money, a bold total with a
rule above it, and one `width` step at the end fitting every column it touched.

The one thing it is told **not** to do is decorate. Colour marks structure, and
a model given a palette will stripe every other row with it.

## The checking is where the value is

A plan is a small JSON object that looks fine and can wreck a workbook.

* A tab that is not there is **dropped**; a tab the plan itself created two
  steps earlier is **allowed**.
* A style key nothing declares is dropped **from the step** rather than taking
  the step with it.
* A plan bigger than the store holds is **refused whole**, because half a plan
  applied is a workbook nobody asked for.

## What is not declared here

The writing verbs, which are `oneai/text.py`'s. A sheet is not prose, so it
uses few of them — but `intelligence.suggest_sources` is this module's door
onto the shared machinery for "which record is this about".

## What a tenant configures

`sheet.plan` appears in `OneAI Settings` like any other feature: on or off, a
model, options, and a `prompt_addendum`. A workspace whose quotes have a house
layout says so there once.

## Where the door is, on screen

In the menu, with the other verbs, and there is no branded button. This module
settled that first and OneWriter followed: `shared/lib/ai/verbs.js` holds the
words and their order so the three editors cannot drift, and the panel knows
which window is in front.
