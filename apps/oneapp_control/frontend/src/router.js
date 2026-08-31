import { createRouter, createWebHistory } from 'vue-router'

/**
 * Signing up, and nothing else.
 *
 * This app served two full SPAs — `/admin` for operators and `/portal` for
 * customers. Both are Spaces now, rendered by OneSpace on this same site, so
 * what is left is the one page somebody reaches *before* they have an account:
 * `/one` sends a Guest to sign in, correctly, and this cannot.
 *
 * The history base is the route rather than '/', because unlike the two
 * surfaces this replaced there is only one of them.
 */
const routes = [
  {
    path: '/',
    name: 'Signup',
    component: () => import('./pages/signup/SignupPage.vue'),
  },
  {
    path: '/welcome',
    name: 'SignupWelcome',
    component: () => import('./pages/signup/SignupWelcome.vue'),
  },
  // Anything else here is a link from before this became one page. Sending it
  // to signup is friendlier than a 404: whoever followed it was on their way to
  // an account either way, and the sign-in page is one step from here.
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHistory('/signup'),
  routes,
})

export default router
