import { describe, it, expect } from 'vitest';
import { taskStatusBadge, recurrenceLabel, groupActiveTasks } from './taskStatus';

describe('taskStatusBadge', () => {
  it('maps flat computed statuses to a badge, or null when none is warranted', () => {
    expect(taskStatusBadge({ computed_status: 'done' })).toEqual({ label: 'Done', color: 'green' });
    expect(taskStatusBadge({ computed_status: 'dormant' })).toEqual({ label: 'Waiting', color: 'purple' });
    // A plain present task shows no badge — its cadence is displayed separately.
    expect(taskStatusBadge({ computed_status: 'present' })).toBeNull();
  });
});

describe('recurrenceLabel', () => {
  it('describes each cadence (or a dateless to-do)', () => {
    expect(recurrenceLabel({ recurrence_type: 'none' })).toBe('To-do');
    expect(recurrenceLabel({ recurrence_type: 'daily' })).toBe('Daily');
    expect(recurrenceLabel({ recurrence_type: 'weekly' })).toBe('Weekly');
    expect(recurrenceLabel({ recurrence_type: 'interval', recurrence_interval: 3 })).toBe('Every 3 days');
    expect(recurrenceLabel({ recurrence_type: 'interval', recurrence_interval: 1 })).toBe('Daily');
  });
});

describe('groupActiveTasks', () => {
  it('buckets active tasks into Reminders then To-do, sorted by name', () => {
    const tasks = [
      { task_id: 'a', name: 'Weed beds', recurrence_type: 'weekly' },
      { task_id: 'b', name: 'Fix latch', recurrence_type: 'none' },
      { task_id: 'c', name: 'Feed hens', recurrence_type: 'daily' },
      { task_id: 'd', name: 'Call vet', recurrence_type: 'none' },
    ];

    const groups = groupActiveTasks(tasks);

    expect(groups.map((g) => g.key)).toEqual(['reminders', 'todo']);
    const reminders = groups.find((g) => g.key === 'reminders');
    expect(reminders.tasks.map((t) => t.task_id)).toEqual(['c', 'a']); // Feed hens, Weed beds
    const todo = groups.find((g) => g.key === 'todo');
    expect(todo.tasks.map((t) => t.task_id)).toEqual(['d', 'b']); // Call vet, Fix latch
  });

  it('omits empty groups', () => {
    const groups = groupActiveTasks([{ task_id: 'x', name: 'Solo', recurrence_type: 'daily' }]);
    expect(groups.map((g) => g.key)).toEqual(['reminders']);
  });
});
