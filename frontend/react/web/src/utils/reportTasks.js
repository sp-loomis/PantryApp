/**
 * reportTasks — reconcile frozen report task snapshots with live task state.
 *
 * A report message stores task rows as a point-in-time snapshot (`task_id`,
 * `done`, `computed_status`, `current_due` as they were when the report ran).
 * The single-report page overlays the *live* task state so its checkboxes read
 * true even if a task changed after the report ran. Report membership (which
 * tasks are listed) stays frozen; only per-task state is refreshed.
 */

/**
 * Index a live task list by `task_id` for O(1) lookup.
 * @param {Array<{task_id: string}>} tasks
 * @returns {Map<string, object>}
 */
export function buildTaskState(tasks = []) {
  const map = new Map();
  for (const task of tasks) {
    if (task && task.task_id != null) map.set(task.task_id, task);
  }
  return map;
}

/**
 * Resolve the row to render for a snapshot item, preferring live task state.
 *
 * When the task still exists (present in `taskState`), its live `done`,
 * `computed_status` and `current_due` win over the snapshot. When it's gone
 * (deleted since the report ran), we fall back to the snapshot and flag it so
 * the UI can disable its checkbox instead of firing a request that 404s.
 *
 * `answer_mode`/`last_decision` (live-preferred) let the UI pick the right
 * control — a Yes/No button pair for a `yesno` decision task, a checkbox
 * otherwise — and show which way a decision was answered.
 *
 * @param {object} item - the snapshot task dict from message.sections[].content.items
 * @param {Map<string, object>} taskState - live tasks by id
 * @returns {{task_id, name, done, computed_status, current_due, answer_mode, last_decision, exists}}
 */
export function resolveTaskRow(item, taskState) {
  const live = taskState?.get(item.task_id);
  const source = live || item;
  return {
    task_id: item.task_id,
    name: item.name,
    done: Boolean(source.done),
    computed_status: source.computed_status,
    current_due: source.current_due,
    answer_mode: source.answer_mode || 'checkbox',
    last_decision: source.last_decision ?? null,
    exists: Boolean(live),
  };
}
