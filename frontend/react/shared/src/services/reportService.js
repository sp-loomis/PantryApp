/**
 * Report service
 *
 * One function per backend endpoint for scheduled reports. Each unwraps the
 * single-key response envelope. Running a report renders its section rules
 * (task/item queries) server-side in the caller's timezone, so `runReport`
 * sends the browser's IANA timezone.
 *
 * Platform-agnostic — usable from web and future mobile.
 */

import { api } from './apiClient.js';

/** The caller's IANA timezone (e.g. "America/New_York"), or undefined. */
function clientTz() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

export async function listReports() {
  const data = await api.get('/reports');
  return data.reports;
}

export async function getReport(reportId) {
  const data = await api.get(`/reports/${reportId}`);
  return data.report;
}

/**
 * Create a report.
 * @param {{name, schedule, sections?, enabled?, delivery?, trigger?}} payload
 *   schedule: { frequency: 'daily'|'weekly'|'monthly', time_of_day: 'HH:MM',
 *               weekday?: 0-6, day_of_month?: 1-28, tz: string }
 *   sections: [{ type: 'custom_message'|'task_query'|'item_query', heading, config }]
 *   trigger (optional conditional gate — the report generates on schedule only when
 *     the trigger passes against live data; empty = always generate):
 *     { match: 'all'|'any',
 *       conditions: [{ query: { location_id?, tags?, name? },
 *                      match: 'all'|'any',
 *                      inequalities: [{ category_id, operator: 'below'|'above', threshold }] }] }
 */
export async function createReport(payload) {
  const data = await api.post('/reports', payload);
  return data.report;
}

export async function updateReport(reportId, updates) {
  const data = await api.put(`/reports/${reportId}`, updates);
  return data.report;
}

export async function deleteReport(reportId) {
  return api.del(`/reports/${reportId}`);
}

/** Generate a report now; returns the created message. */
export async function runReport(reportId) {
  const data = await api.post(`/reports/${reportId}/run`, undefined, {
    query: { tz: clientTz() },
  });
  return data.message;
}

/**
 * Re-render a report's sections against live data, without persisting a message
 * or delivering to Slack. Used by the interactive report page to surface the
 * next round of tasks after a decision is answered.
 * @returns rendered sections in the same shape as `message.sections`.
 */
export async function previewReport(reportId) {
  const data = await api.post(`/reports/${reportId}/preview`, undefined, {
    query: { tz: clientTz() },
  });
  return data.sections;
}
