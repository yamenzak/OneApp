/**
 * One person, beyond what their record holds.
 *
 * Where somebody is *now* and how they have been are not fields on an Employee:
 * they are four HRMS doctypes reasoned over, which is `oneapp/onehr/presence.py`
 * and `history.py`. A record page asks for them here rather than assembling them
 * from four lists, because the ranking between those four — leave outranks a
 * badge-in, a holiday outranks both — is a product decision and belongs in one
 * place on the server.
 *
 * Silent, both of them. A workspace without HRMS answers "not known" and draws
 * nothing, and a toast saying so on every person you open would be a toast about
 * an app the reader never asked for.
 */

import { callMethod } from '@/shared/lib/runtime/resource'

export const people = {
  /** In, out, on leave, on holiday, absent — and whether an arrival was late. */
  presence: (employee) =>
    callMethod('oneapp.onehr.presence.of', { employee }, { silent: true, method: 'GET' }),

  /** Their last eight weeks of days, and the leave they have left by type. */
  personHistory: (employee) =>
    callMethod('oneapp.onehr.history.of', { employee }, { silent: true, method: 'GET' }),

  /**
   * The reader's own page, whole — `oneapp/onehr/me.py`.
   *
   * No argument, and that is the security property rather than an economy:
   * there is no employee to pass, so there is no employee to pass somebody
   * else's. Silent like the two above, because a workspace without HRMS
   * answers "nobody" and the page says so in a sentence.
   */
  myHr: () => callMethod('oneapp.onehr.me.home', {}, { silent: true, method: 'GET' }),

  /** Which way the check-in control points, or nothing where it should not
   *  be offered at all. Read again after every file, so the button and the
   *  pill above it cannot disagree. */
  checkInDirection: () =>
    callMethod('oneapp.onehr.checkin.next_direction', {}, { silent: true, method: 'GET' }),

  /**
   * File one, for the person asking.
   *
   * Not silent: this is the one write in OneHR, and a check-in that was
   * refused — you are on leave, the workspace keeps no check-ins — is a
   * sentence the person pressing the button needs to read.
   */
  checkIn: (where = {}) => callMethod('oneapp.onehr.checkin.file', where),

  /**
   * The address this reader's request arrives from — `oneapp/onehr/place.py`.
   *
   * For the control that offers to use it rather than have somebody look it
   * up. It discloses only what the caller is already sending, so there is
   * nothing to guard beyond being signed in.
   */
  networkHere: () =>
    callMethod('oneapp.onehr.place.detect', {}, { silent: true, method: 'GET' }),

  /**
   * One day's roll, with everything already known about it filled in —
   * `oneapp/onehr/roster.py`. Who is on leave, whose day is a holiday, who has
   * already been marked and who clocked in late.
   */
  rollCall: (on = '') =>
    callMethod('oneapp.onehr.roster.day', { on }, { silent: true, method: 'GET' }),

  /**
   * Write the day. Not silent: this is a register being taken, and a row HRMS
   * declined — somebody marked that day while the page was open — is a
   * sentence the person pressing the button needs.
   */
  markDay: (on, marks) =>
    callMethod('oneapp.onehr.roster.mark', { on, marks: JSON.stringify(marks) }),

  /**
   * The three HRMS bulk tools this space puts a door on —
   * `oneapp/onehr/tools.py`. The first call is the doctype's own form, as
   * columns and a layout; the two settings pages that used to share it are the
   * engine's now, through `singlePage`.
   */
  hrPage: (screen) =>
    callMethod('oneapp.onehr.tools.page', { screen },
               { silent: true, method: 'GET' }),

  /** Who the filters at the top of a tool describe. Silent: an empty answer is
   *  an answer, and it is the one the page renders as "nobody left to do". */
  hrPeople: (screen, values) =>
    callMethod('oneapp.onehr.tools.people',
               { screen, values: JSON.stringify(values) }, { silent: true }),

  /** And do it. Not silent: HRMS names the field it wanted and the person who
   *  could not be done, and both are sentences the presser needs. */
  hrRun: (screen, values, chosen) =>
    callMethod('oneapp.onehr.tools.run', {
      screen, values: JSON.stringify(values), chosen: JSON.stringify(chosen),
    }),
}
