/**
 * OneCloud's place on the desk.
 *
 * Its own module so that the dock, the window and anything that wants to open
 * a folder beside what somebody is doing all name it the same thing — and so
 * that `apps.js`, which knows about every app, does not have to import a
 * component to find out what one is called.
 */

/** The window id, which is also its dock tile and its remembered corner. */
export const DRIVE = 'onestorage'
