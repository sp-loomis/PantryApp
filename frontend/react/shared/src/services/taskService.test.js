import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the HTTP layer so we exercise the service's envelope + query handling.
const get = vi.fn();
const post = vi.fn();
vi.mock('./apiClient.js', () => ({
  api: {
    get: (...args) => get(...args),
    post: (...args) => post(...args),
  },
}));

const { listTasks, completeTask } = await import('./taskService.js');

describe('listTasks', () => {
  beforeEach(() => {
    get.mockReset();
  });

  it('unwraps the tasks envelope and sends a tz + status filter', async () => {
    get.mockResolvedValue({ tasks: [{ task_id: 'a' }] });

    const result = await listTasks({ status: 'active' });

    expect(result).toEqual([{ task_id: 'a' }]);
    const [path, options] = get.mock.calls[0];
    expect(path).toBe('/tasks');
    expect(options.query.status).toBe('active');
    expect('tz' in options.query).toBe(true);
  });

  it('omits the status filter when listing all', async () => {
    get.mockResolvedValue({ tasks: [] });

    await listTasks({ status: 'all' });

    const [, options] = get.mock.calls[0];
    expect('status' in options.query).toBe(false);
  });
});

describe('completeTask', () => {
  beforeEach(() => {
    post.mockReset();
  });

  it('posts to the complete endpoint with a tz and returns the task', async () => {
    post.mockResolvedValue({ task: { task_id: 'a', done: true } });

    const result = await completeTask('a');

    expect(result).toEqual({ task_id: 'a', done: true });
    const [path, body, options] = post.mock.calls[0];
    expect(path).toBe('/tasks/a/complete');
    expect(body).toBeUndefined();
    expect('tz' in options.query).toBe(true);
  });
});
