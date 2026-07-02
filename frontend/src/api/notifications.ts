import { api } from './client'

export function sendTestEmail(email: string) {
  return api.post('/notifications/test-email', { email }).then(r => r.data)
}

export function getSmtpStatus() {
  return api.get('/notifications/smtp-status').then(r => r.data)
}
