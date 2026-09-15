import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the HTTP layer so we exercise the service's path + envelope handling.
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
  getAuthorizeUrl,
  listConnections,
  listChannels,
  disconnect,
  testConnection,
} = await import('./slackService.js');

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  del.mockReset();
});

describe('getAuthorizeUrl', () => {
  it('unwraps the authorize_url from /slack/oauth/start', async () => {
    get.mockResolvedValue({ authorize_url: 'https://slack.com/oauth/v2/authorize?x=1' });
    const url = await getAuthorizeUrl();
    expect(url).toBe('https://slack.com/oauth/v2/authorize?x=1');
    expect(get.mock.calls[0][0]).toBe('/slack/oauth/start');
  });
});

describe('listConnections', () => {
  it('unwraps the connections envelope', async () => {
    get.mockResolvedValue({ connections: [{ connection_id: 'c1' }] });
    const result = await listConnections();
    expect(result).toEqual([{ connection_id: 'c1' }]);
    expect(get.mock.calls[0][0]).toBe('/slack/connections');
  });
});

describe('listChannels', () => {
  it('requests the connection channels path', async () => {
    get.mockResolvedValue({ channels: [{ id: 'C1', name: 'general' }] });
    const result = await listChannels('c1');
    expect(result).toEqual([{ id: 'C1', name: 'general' }]);
    expect(get.mock.calls[0][0]).toBe('/slack/connections/c1/channels');
  });
});

describe('disconnect', () => {
  it('deletes the connection', async () => {
    del.mockResolvedValue({ deleted: true });
    await disconnect('c1');
    expect(del.mock.calls[0][0]).toBe('/slack/connections/c1');
  });
});

describe('testConnection', () => {
  it('posts the channel_id to the test endpoint', async () => {
    post.mockResolvedValue({ ok: true });
    await testConnection('c1', 'C_GENERAL');
    const [path, body] = post.mock.calls[0];
    expect(path).toBe('/slack/connections/c1/test');
    expect(body).toEqual({ channel_id: 'C_GENERAL' });
  });
});
