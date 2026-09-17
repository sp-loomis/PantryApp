import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the HTTP layer so we exercise the service's envelope handling.
const get = vi.fn();
const post = vi.fn();
const del = vi.fn();
vi.mock('./apiClient.js', () => ({
  api: {
    get: (...args) => get(...args),
    post: (...args) => post(...args),
    del: (...args) => del(...args),
  },
}));

const {
  listMessages,
  listUnread,
  getMessage,
  markRead,
  markUnread,
  deleteMessage,
  markAllRead,
  deleteMessages,
} = await import('./messageService.js');

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  del.mockReset();
});

describe('listMessages', () => {
  it('unwraps the messages envelope', async () => {
    get.mockResolvedValue({ messages: [{ message_id: 'm1' }] });
    expect(await listMessages()).toEqual([{ message_id: 'm1' }]);
    expect(get.mock.calls[0][0]).toBe('/messages');
  });
});

describe('listUnread', () => {
  it('returns messages and count from the unread endpoint', async () => {
    get.mockResolvedValue({ messages: [{ message_id: 'm1' }], unread_count: 1 });
    const result = await listUnread();
    expect(result).toEqual({ messages: [{ message_id: 'm1' }], unread_count: 1 });
    expect(get.mock.calls[0][0]).toBe('/messages/unread');
  });
});

describe('getMessage', () => {
  it('unwraps the single message envelope', async () => {
    get.mockResolvedValue({ message: { message_id: 'm1' } });
    expect(await getMessage('m1')).toEqual({ message_id: 'm1' });
    expect(get.mock.calls[0][0]).toBe('/messages/m1');
  });
});

describe('markRead / markUnread', () => {
  it('posts to the read endpoint', async () => {
    post.mockResolvedValue({ message: { message_id: 'm1', read_at: 'now' } });
    const result = await markRead('m1');
    expect(result.read_at).toBe('now');
    expect(post.mock.calls[0][0]).toBe('/messages/m1/read');
  });

  it('posts to the unread endpoint', async () => {
    post.mockResolvedValue({ message: { message_id: 'm1', read_at: null } });
    const result = await markUnread('m1');
    expect(result.read_at).toBeNull();
    expect(post.mock.calls[0][0]).toBe('/messages/m1/unread');
  });
});

describe('deleteMessage', () => {
  it('deletes the message path', async () => {
    del.mockResolvedValue({ message: 'deleted' });
    await deleteMessage('m1');
    expect(del.mock.calls[0][0]).toBe('/messages/m1');
  });
});

describe('markAllRead', () => {
  it('posts the id list to the bulk read endpoint', async () => {
    post.mockResolvedValue({ updated: 2 });
    const result = await markAllRead(['m1', 'm2']);
    expect(result).toEqual({ updated: 2 });
    expect(post.mock.calls[0][0]).toBe('/messages/read-all');
    expect(post.mock.calls[0][1]).toEqual({ message_ids: ['m1', 'm2'] });
  });
});

describe('deleteMessages', () => {
  it('sends the id list as the delete body', async () => {
    del.mockResolvedValue({ deleted: 2 });
    const result = await deleteMessages(['m1', 'm2']);
    expect(result).toEqual({ deleted: 2 });
    expect(del.mock.calls[0][0]).toBe('/messages');
    expect(del.mock.calls[0][1]).toEqual({ body: { message_ids: ['m1', 'm2'] } });
  });
});
