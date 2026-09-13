/**
 * Task service
 *
 * One function per backend endpoint for tasks/chores. Each unwraps the
 * single-key response envelope. Task windows (today / this week / interval
 * slots) are computed server-side in the caller's timezone, so every read and
 * completion sends the browser's IANA timezone.
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

/**
 * List tasks with computed urgency status.
 * @param {{status?: 'active'|'done'|'all', tag?: string}} [opts]
 * @returns tasks, each carrying `computed_status`, `current_due`,
 *   `due_in_days`, `done` and `active`.
 */
export async function listTasks({ status = 'active', tag } = {}) {
  const query = { tz: clientTz(), tag };
  // 'all' means "no status filter"; the backend treats an absent status as all.
  if (status && status !== 'all') query.status = status;
  const data = await api.get('/tasks', { query });
  return data.tasks;
}

export async function getTask(taskId) {
  const data = await api.get(`/tasks/${taskId}`, { query: { tz: clientTz() } });
  return data.task;
}

/**
 * Create a task.
 * @param {{name, notes?, tags?, recurrence_type?, recurrence_interval?, anchor_date?, due_date?, graceful?}} payload
 */
export async function createTask(payload) {
  const data = await api.post('/tasks', payload, { query: { tz: clientTz() } });
  return data.task;
}

export async function updateTask(taskId, updates) {
  const data = await api.put(`/tasks/${taskId}`, updates, { query: { tz: clientTz() } });
  return data.task;
}

export async function deleteTask(taskId) {
  return api.del(`/tasks/${taskId}`);
}

/** Mark a task complete for its current window. */
export async function completeTask(taskId) {
  const data = await api.post(`/tasks/${taskId}/complete`, undefined, { query: { tz: clientTz() } });
  return data.task;
}

/** Undo completion of a task for its current window. */
export async function uncompleteTask(taskId) {
  const data = await api.post(`/tasks/${taskId}/uncomplete`, undefined, { query: { tz: clientTz() } });
  return data.task;
}
