import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'ReportList',
    component: () => import('./views/ReportList.vue'),
  },
  {
    path: '/report/:filename',
    name: 'ReportDetail',
    component: () => import('./views/ReportDetail.vue'),
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
