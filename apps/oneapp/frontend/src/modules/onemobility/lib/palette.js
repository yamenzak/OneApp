/**
 * One colour vocabulary for the map and the charts.
 *
 * The network screen and the Insights screen are two views of the same
 * numbers, and until this file they picked their colours separately — the map
 * with hardcoded hex, the charts with whatever frappe-ui's default ramp gave
 * them. So a bus that was amber on the map sat in a blue bar on the chart, and
 * a reader had to learn the encoding twice.
 *
 * Everything here comes out of the design system's own ramps, read from the
 * document so both themes are right without either being written down:
 *
 *   occupancy   an ordinal *state*, not a magnitude. Transit already has this
 *               vocabulary — GTFS-RT calls it `OccupancyStatus` — and every
 *               operator reads seats-free/standing/crush at a glance. Five
 *               steps, each with a name, always drawn with the legend beside
 *               them so it is never colour alone.
 *   delay       diverging, because it has a meaningful zero: early and late are
 *               opposite failures and the middle is the timetable being kept.
 *               Never a single ramp — that would draw a minute early and a
 *               minute late as if they were the same distance from nothing.
 *   line        categorical, and a line's *own* colour first: an operator has
 *               spent decades teaching people that the 100 is red, and no
 *               palette of ours outranks that. The ramp is the fallback, in
 *               fixed order, for a line whose feed declares nothing.
 */

import { onDark, paintable, tokenInk } from '@/modules/onespace/lib/screen/ink'
import { __ } from '@/shared/lib/runtime/translate'

/**
 * How full, in the five steps a transit feed actually reports.
 *
 * `floor` is the lowest percentage in the band. Ordered loosest first so a
 * lookup is a scan from the end.
 *
 * **Each band names a token per ground, and that is not belt-and-braces.** This
 * theme's dark ramp is not a mirror of its light one — `ink-red-8` is L .44 on
 * white and L .87 on black, so a scale that names one token per band separates
 * on one ground and collapses on the other. Measured: the four bands as one
 * token set came back with yellow and orange at ΔE 1.8 under deuteranopia in
 * dark mode, which is no distinction at all.
 *
 * Both rows were chosen by running `dataviz/scripts/validate_palette.js` rather
 * than by eye, and both pass its separation checks:
 *
 *     light  green-4 yellow-5 orange-6 red-8   worst adjacent ΔE 16.1 normal, 11.8 CVD
 *     dark   green-6 yellow-7 orange-7 red-5   worst adjacent ΔE 17.8 normal, 13.8 CVD
 *
 * What it replaced failed four checks and had green against teal at ΔE 4.6 for
 * *normal* vision — two bands nobody could tell apart, colourblind or not. The
 * cause was that every band used `ink-*-3`, the palest step in each ramp: a
 * step meant to tint a background behind text, asked to be identified at
 * sixteen pixels on a map.
 *
 * The progression is ordinal and reads as one: it warms green → yellow →
 * orange → red as the vehicle fills, and it moves *away* from the ground —
 * darker on white, lighter on black — so fuller is always the higher-contrast
 * thing on the screen. `unknown` sits outside the ramp in plain grey, because
 * "nobody counted" is not a quantity and must not look like one.
 */
export const OCCUPANCY = [
  { key: 'unknown', floor: -1, light: '--ink-gray-4', dark: '--ink-gray-6',
    label: () => __('Not counted') },
  { key: 'free', floor: 0, light: '--ink-green-4', dark: '--ink-green-6',
    label: () => __('Seats free') },
  { key: 'filling', floor: 40, light: '--ink-yellow-5', dark: '--ink-yellow-7',
    label: () => __('Filling up') },
  { key: 'standing', floor: 70, light: '--ink-orange-6', dark: '--ink-orange-7',
    label: () => __('Standing') },
  { key: 'crush', floor: 90, light: '--ink-red-8', dark: '--ink-red-5',
    label: () => __('Crush') },
]

/** A band's colour on whichever ground the reader is actually on. */
export function bandInk(band) {
  return tokenInk(onDark() ? band.dark : band.light, '#8b8b8b')
}

/** The band a percentage falls in. -1 means the feed did not say. */
export function occupancyBand(percent) {
  const value = Number(percent)
  if (!Number.isFinite(value) || value < 0) return OCCUPANCY[0]
  let found = OCCUPANCY[1]
  for (const band of OCCUPANCY) {
    if (band.floor >= 0 && value >= band.floor) found = band
  }
  return found
}

/** That band, as something a canvas or a style specification can paint with. */
export function occupancyInk(percent) {
  return bandInk(occupancyBand(percent))
}

/**
 * The whole scale, for a legend. Built at call time rather than at import,
 * because a theme change has to move it and a module constant would not.
 */
export function occupancyScale() {
  return OCCUPANCY.map((band) => ({
    key: band.key,
    label: band.label(),
    ink: bandInk(band),
    floor: band.floor,
  }))
}

/**
 * The diverging ramp, coolest first. Nine steps with a near-neutral middle.
 *
 * Read off the document so it follows the theme. The fallbacks are the light
 * ramp's own values, for the one case where there is no document to read —
 * a unit test.
 */
const DIVERGING = [
  '#366ea3', '#5b8ec1', '#81b0de', '#a9d2fb', '#fbf1c7',
  '#eec88c', '#e09e62', '#ce7249', '#b5473f',
]

export function divergingRamp() {
  return DIVERGING.map((fallback, at) => tokenInk(`--chart-diverging-${at + 1}`, fallback))
}

/**
 * Seconds behind the timetable as a colour. Negative is early.
 *
 * `span` is the delay that saturates the scale — anything worse is drawn as
 * the end of it rather than off it. Five minutes by default, which is the
 * threshold most European authorities report punctuality against, so the
 * ramp's warm end lines up with the number in the headline figure.
 */
export function delayInk(seconds, span = 300) {
  const ramp = divergingRamp()
  const value = Number(seconds)
  if (!Number.isFinite(value)) return ramp[4]
  const clamped = Math.max(-1, Math.min(1, value / span))
  const at = Math.round((clamped + 1) * 0.5 * (ramp.length - 1))
  return ramp[at]
}

/** The categorical ramp, in the order a series must take it. */
const CATEGORICAL = [
  '#2283c3', '#84c5f9', '#289e60', '#84d4a1', '#753cbb',
  '#bb9df1', '#c98c28', '#f5ca8e', '#ba205a', '#f98da7',
]

export function categoricalRamp() {
  return CATEGORICAL.map((fallback, at) => tokenInk(`--chart-categorical-${at + 1}`, fallback))
}

/**
 * A line's colour: its own, or the next slot of the ramp.
 *
 * `at` is the line's position in the network's own ordering, so the ramp is
 * assigned in fixed order and a filter that hides one line never repaints the
 * others.
 */
export function lineInk(line, at = 0) {
  const declared = (line?.colour || '').trim()
  if (declared) return paintable(declared, CATEGORICAL[0])
  const ramp = categoricalRamp()
  return ramp[at % ramp.length]
}

/**
 * How a route line is drawn: the colour, and the casing under it.
 *
 * Every transit map in the world draws a route as a wide neutral stroke with
 * a narrower coloured one on top. It is not decoration — it is what keeps two
 * lines legible where they run together, and what stops a red route
 * disappearing into a dark basemap. The casing is the surface colour, so it
 * reads as the map breathing around the line in both themes.
 */
export function casingInk() {
  return tokenInk('--surface-elevation-2', '#ffffff')
}
