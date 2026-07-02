import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/forgot-password',
      name: 'ForgotPassword',
      component: () => import('@/views/ForgotPasswordView.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/DashboardView.vue') },
        { path: 'scripts', name: 'Scripts', component: () => import('@/views/ScriptListView.vue') },
        { path: 'scripts/new', name: 'ScriptNew', component: () => import('@/views/ScriptEditor.vue') },
        { path: 'scripts/:id/edit', name: 'ScriptEdit', component: () => import('@/views/ScriptEditor.vue') },
        { path: 'scripts/:id/execute', name: 'ScriptExecute', component: () => import('@/views/ScriptExecute.vue') },
        { path: 'credentials', name: 'Credentials', component: () => import('@/views/CredentialListView.vue') },
        { path: 'executions', name: 'Executions', component: () => import('@/views/ExecutionHistory.vue') },
        { path: 'system/notifications', name: 'Notifications', component: () => import('@/views/NotificationsView.vue') },
      ],
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (to.meta.guest) {
    next()
    return
  }
  if (!auth.token) {
    next('/login')
    return
  }
  next()
})

export default router
