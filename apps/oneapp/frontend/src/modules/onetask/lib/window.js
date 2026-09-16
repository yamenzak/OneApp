/**
 * OneTask's place on the desk.
 *
 * As small as the diary's and for the same reason: the applet keeps nothing
 * between openings — what it shows is two queries and a clock, all three read
 * fresh when it opens, because the point of a window you keep beside your work
 * is that it is right rather than that it is fast to reopen.
 *
 * Its own module because `apps.js` knows about every app and must not import a
 * component to find out what one is called.
 */
export const TASKS = 'onetask'
