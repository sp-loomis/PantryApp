import { describe, it, expect } from 'vitest';
import { buildTaskState, resolveTaskRow } from './reportTasks';

describe('buildTaskState', () => {
  it('indexes tasks by task_id', () => {
    const map = buildTaskState([
      { task_id: 'a', done: false },
      { task_id: 'b', done: true },
    ]);
    expect(map.size).toBe(2);
    expect(map.get('a')).toEqual({ task_id: 'a', done: false });
    expect(map.get('b').done).toBe(true);
  });

  it('tolerates empty/undefined input and skips id-less entries', () => {
    expect(buildTaskState().size).toBe(0);
    expect(buildTaskState([{ name: 'no id' }, null]).size).toBe(0);
  });
});

describe('resolveTaskRow', () => {
  const snapshot = {
    task_id: 't1',
    name: 'Water plants',
    done: false,
    computed_status: 'due_today',
    current_due: '2026-09-18',
  };

  it('prefers live task state over the frozen snapshot when the task exists', () => {
    const state = buildTaskState([
      { task_id: 't1', done: true, computed_status: 'done', current_due: '2026-09-25' },
    ]);
    expect(resolveTaskRow(snapshot, state)).toEqual({
      task_id: 't1',
      name: 'Water plants',
      done: true,
      computed_status: 'done',
      current_due: '2026-09-25',
      exists: true,
    });
  });

  it('falls back to the snapshot and flags exists=false when the task is gone', () => {
    const row = resolveTaskRow(snapshot, buildTaskState([]));
    expect(row.done).toBe(false);
    expect(row.computed_status).toBe('due_today');
    expect(row.current_due).toBe('2026-09-18');
    expect(row.exists).toBe(false);
  });

  it('coerces done to a boolean', () => {
    const row = resolveTaskRow({ ...snapshot, done: undefined }, new Map());
    expect(row.done).toBe(false);
  });
});
