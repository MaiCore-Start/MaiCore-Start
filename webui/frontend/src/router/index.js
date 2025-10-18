import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '../views/Dashboard.vue'
import Instances from '../views/Instances.vue'
import Settings from '../views/Settings.vue'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard
  },
  {
    path: '/instances',
    name: 'Instances',
    component: Instances
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router