import { createRouter, createWebHistory } from 'vue-router'
import Users from '../views/Users.vue'
import Performance from '../views/Performance.vue'
import Login from '../views/Login.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', redirect: '/users' },
    { path: '/users', component: Users, meta: { requiresAuth: true } },
    { path: '/performance', component: Performance },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !localStorage.getItem('sv_token')) {
    return '/login'
  }
})

export default router
