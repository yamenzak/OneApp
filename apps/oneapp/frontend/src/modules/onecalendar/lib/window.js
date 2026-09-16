/**
 * The diary's place on the desk.
 *
 * Smaller than mail's and OneCloud's, because the diary keeps nothing: it has
 * no folder, no open item and no place — the grid decides which weeks to fetch
 * from what it is showing, and what it is showing is the grid's own state. So
 * there is an id and nothing else.
 *
 * Its own module for the reason the other two have one: `apps.js` knows about
 * every app and must not import a component to find out what one is called.
 */
export const DIARY = 'onecalendar'
