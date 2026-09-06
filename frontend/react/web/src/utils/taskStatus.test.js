import { describe, it, expect } from 'vitest';
import { taskStatusBadge, recurrenceLabel, groupActiveTasks } from './taskStatus';

describe('taskStatusBadge', () => {
  it('maps computed statuses to the expected color/label', () => {
    expect(taskStatusBadge({ computed_status: 'overdue' })).toEqual({ label: 'Overdue', color: 'red' });
    expect(taskStatusBadge({ computed_status: 'due_today' })).toEqual({ label: 'Today', color: 'red' });
    expect(taskStatusBadge({ computed_status: 'due_soon', due_in_days: 3 })).toEqual({ label: '3d left', color: 'orange' });
    expect(taskStatusBadge({ computed_status: 'due_soon', due_in_days: 1 })).toEqual({ label: 'Tomorrow', color: 'orange' });
    expect(taskStatusBadge({ computed_status: 'done' })).toEqual({ label: 'Done', color: 'green' });
    expect(taskStatusBadge({ computed_status: 'upcoming', due_in_days: null })).toEqual({ label: 'Someday', color: 'gray' });
  });
});

describe('recurrenceLabel', () => {
  it('describes each recurrence type', () => {
    expect(recurrenceLabel({ recurrence_type: 'none' })).toBe('One-time');
    expect(recurrenceLabel({ recurrence_type: 'daily' })).toBe('Daily');
    expect(recurrenceLabel({ recurrence_type: 'weekly' })).toBe('Weekly');
    expect(recurrenceLabel({ recurrence_type: 'interval', recurrence_interval: 3 })).toBe('Every 3 days');
    expect(recurrenceLabel({ recurrence_type: 'interval', recurrence_interval: 1 })).toBe('Daily');
  });
});

describe('groupActiveTasks', () => {
  it('buckets tasks into ordered non-empty urgency groups, sorted by due', () => {
    const tasks = [
      { task_id: 'a', computed_status: 'due_soon', due_in_days: 5 },
      { task_id: 'b', computed_status: 'overdue', due_in_days: -2 },
      { task_id: 'c', computed_status: 'due_soon', due_in_days: 2 },
      { task_id: 'd', computed_status: 'due_today', due_in_days: 0 },
    ];

    const groups = groupActiveTasks(tasks);

    expect(groups.map((g) => g.key)).toEqual(['overdue', 'today', 'week']);
    // "This week" group sorted by soonest due first.
    const week = groups.find((g) => g.key === 'week');
    expect(week.tasks.map((t) => t.task_id)).toEqual(['c', 'a']);
  });

  it('omits empty groups', () => {
    const groups = groupActiveTasks([{ task_id: 'x', computed_status: 'upcoming', due_in_days: 30 }]);
    expect(groups.map((g) => g.key)).toEqual(['upcoming']);
  });
});
