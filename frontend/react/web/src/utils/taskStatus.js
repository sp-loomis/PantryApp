/**
 * Task status → UI helpers.
 *
 * The backend computes each task's `computed_status` in the caller's timezone
 * (see backend/recurrence.py), so the client trusts it rather than recomputing.
 * The badge palette mirrors utils/dates.js `expiryStatus`: overdue/today = red,
 * due-soon = orange, otherwise gray; completed = green.
 */

/** Badge descriptor ({label, color}) for a task's computed status. */
export function taskStatusBadge(task) {
  const days = task.due_in_days;
  switch (task.computed_status) {
    case 'overdue':
      return { label: 'Overdue', color: 'red' };
    case 'due_today':
      return { label: 'Today', color: 'red' };
    case 'due_soon':
      return { label: days === 1 ? 'Tomorrow' : `${days}d left`, color: 'orange' };
    case 'done':
      return { label: 'Done', color: 'green' };
    case 'upcoming':
    default:
      return days != null ? { label: `${days}d`, color: 'gray' } : { label: 'Someday', color: 'gray' };
  }
}

/** Human label for a task's recurrence rule. */
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
      return 'One-time';
  }
}

// Urgency groups for the dashboard, in display order. Each active task's
// computed_status maps to exactly one group.
export const TASK_GROUPS = [
  { key: 'overdue', title: 'Overdue', statuses: ['overdue'] },
  { key: 'today', title: 'Today', statuses: ['due_today'] },
  { key: 'week', title: 'This week', statuses: ['due_soon'] },
  { key: 'upcoming', title: 'Upcoming', statuses: ['upcoming'] },
];

/**
 * Split active tasks into ordered urgency groups.
 * @param {object[]} tasks active tasks (already filtered to `active === true`)
 * @returns {{key, title, tasks}[]} non-empty groups in display order
 */
export function groupActiveTasks(tasks) {
  const byDue = (a, b) => {
    const da = a.due_in_days ?? Infinity;
    const db = b.due_in_days ?? Infinity;
    return da - db;
  };
  return TASK_GROUPS
    .map((group) => ({
      ...group,
      tasks: tasks.filter((t) => group.statuses.includes(t.computed_status)).sort(byDue),
    }))
    .filter((group) => group.tasks.length > 0);
}
