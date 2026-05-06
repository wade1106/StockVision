import { createRouter, createWebHistory } from 'vue-router'
import Users from '../views/Users.vue'
import Performance from '../views/Performance.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/users' },
    { path: '/users', component: Users },
    { path: '/performance', component: Performance },
  ],
})
