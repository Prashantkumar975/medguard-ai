import { request as r } from './client'

export const api = {
  // ---- Routes from the implementation plan (section 5) ----
  analytics: () => r('GET', '/analytics/summary'),
  sites: () => r('GET', '/sites'),
  addSite: (body) => r('POST', '/sites', { body }),
  startScan: (body) => r('POST', '/scans', { body }),
  scan: (id) => r('GET', `/scans/${id}`),
  claims: (params) => r('GET', '/claims', { params }),
  incidents: (params) => r('GET', '/incidents', { params }),
  incident: (id) => r('GET', `/incidents/${id}`),
  review: (id, body) => r('POST', `/incidents/${id}/review`, { body }),
  recheck: (id) => r('POST', `/incidents/${id}/recheck`),

  // ---- NOT in the plan yet: the UI needs these, ask backend to add them ----
  scans: (params) => r('GET', '/scans', { params }), // crawl history per site
  updateSite: (id, body) => r('PATCH', `/sites/${id}`, { body }), // enable / disable
  references: (params) => r('GET', '/references', { params }), // Medical Knowledge Library
  users: () => r('GET', '/admin/users'),
  updateUser: (id, body) => r('PATCH', `/admin/users/${id}`, { body }),
  settings: () => r('GET', '/admin/settings'),
  saveSettings: (body) => r('PUT', '/admin/settings', { body }),
}
