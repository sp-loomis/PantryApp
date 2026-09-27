/**
 * Task status → UI helpers.
 *
 * The backend computes each task's flat `computed_status` in the caller's
 * timezone (see backend/recurrence.py): `present` (on the list now), `done`
 * (completed for this window / to-do finished), or `dormant` (a triggered task
 * waiting on its source decision). There is no due-date urgency — a reminder is
 * simply present until marked off and superseded by the next window's instance.
 */

/**
 * Badge descriptor ({label, color}) for a task's computed status, or `null` when
 * no badge is warranted (a plain present task — its cadence is shown separately).
 */
export function taskStatusBadge(task) {
  switch (task.computed_status) {
    case 'done':
      return { label: 'Done', color: 'green' };
    case 'dormant':
      // Triggered task waiting on its source decision (see backend/recurrence.py).
      return { label: 'Waiting', color: 'purple' };
    case 'present':
    default:
      return null;
  }
}

/** Human label for a task's cadence (or "To-do" for a dateless one-shot). */
export function recurrenceLabel(task) {
  switch (task.recurrence_type) {
    case 'daily':
      return 'Daily';
    case 'weekly':
      return 'Weekly';
    case 'interval':
      return task.recurrence_interval === 1 ? 'Daily' : `Every ${task.recurrence_interval} days`;
    case 'none':
    default:
      return 'To-do';
  }
}

// Dashboard groups for active tasks, in display order. Reminders (anything with
// a cadence) come first, then dateless to-dos. Each active task matches exactly
// one group.
export const TASK_GROUPS = [
  { key: 'reminders', title: 'Reminders', match: (t) => t.recurrence_type !== 'none' },
  { key: 'todo', title: 'To-do', match: (t) => t.recurrence_type === 'none' },
];

/**
 * Split active tasks into ordered groups (reminders, then to-dos).
 * @param {object[]} tasks active tasks (already filtered to `active === true`)
 * @returns {{key, title, tasks}[]} non-empty groups in display order
 */
export function groupActiveTasks(tasks) {
  const byName = (a, b) => (a.name || '').localeCompare(b.name || '');
  return TASK_GROUPS
    .map((group) => ({
      key: group.key,
      title: group.title,
      tasks: tasks.filter(group.match).sort(byName),
    }))
    .filter((group) => group.tasks.length > 0);
}
