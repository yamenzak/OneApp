/**
 * OneForms' place on the desk.
 *
 * As small as OneTask's and for the same reason: the service keeps nothing
 * between openings. What it shows is one query, read fresh, because the point
 * of a window beside your work is that it is right rather than fast to reopen.
 *
 * Its own module because `apps.js` knows about every app and must not import a
 * component to find out what one is called.
 */
export const FORMS = 'oneforms'
