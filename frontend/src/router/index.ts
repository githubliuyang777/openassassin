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
        { path: 'profile', name: 'Profile', component: () => import('@/views/ProfileView.vue') },
        { path: 'monitor/domains', name: 'monitor-domains', component: () => import('@/views/DomainCertView.vue') },
        { path: 'subscriptions', name: 'Subscriptions', component: () => import('@/views/SubscriptionView.vue') },
        { path: 'hosts', name: 'Hosts', component: () => import('@/views/HostListView.vue') },
        { path: 'hosts/:id/terminal', name: 'HostTerminal', component: () => import('@/views/HostTerminalView.vue') },
        { path: 'system/audit-logs', name: 'AuditLogs', component: () => import('@/views/AuditLogView.vue') },
        { path: 'system/network-test', name: 'NetworkTest', component: () => import('@/views/NetworkTestView.vue') },
        { path: 'monitor/domains-whois', name: 'monitor-domains-whois', component: () => import('@/views/DomainWhoisView.vue') },
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
