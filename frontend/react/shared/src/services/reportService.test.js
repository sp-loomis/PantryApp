import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the HTTP layer so we exercise the service's envelope + query handling.
const get = vi.fn();
const post = vi.fn();
const put = vi.fn();
const del = vi.fn();
vi.mock('./apiClient.js', () => ({
  api: {
    get: (...args) => get(...args),
    post: (...args) => post(...args),
    put: (...args) => put(...args),
    del: (...args) => del(...args),
  },
}));

const { listReports, createReport, updateReport, runReport, previewReport, deleteReport } =
  await import('./reportService.js');

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  put.mockReset();
  del.mockReset();
});

describe('listReports', () => {
  it('unwraps the reports envelope', async () => {
    get.mockResolvedValue({ reports: [{ report_id: 'r1' }] });
    expect(await listReports()).toEqual([{ report_id: 'r1' }]);
    expect(get.mock.calls[0][0]).toBe('/reports');
  });
});

describe('createReport', () => {
  it('posts the payload and returns the report', async () => {
    post.mockResolvedValue({ report: { report_id: 'r1', name: 'Digest' } });
    const payload = { name: 'Digest', schedule: { frequency: 'daily' }, sections: [] };
    const result = await createReport(payload);
    expect(result).toEqual({ report_id: 'r1', name: 'Digest' });
    const [path, body] = post.mock.calls[0];
    expect(path).toBe('/reports');
    expect(body).toEqual(payload);
  });
});

describe('updateReport', () => {
  it('puts to the report path', async () => {
    put.mockResolvedValue({ report: { report_id: 'r1', name: 'New' } });
    const result = await updateReport('r1', { name: 'New' });
    expect(result.name).toBe('New');
    expect(put.mock.calls[0][0]).toBe('/reports/r1');
  });
});

describe('runReport', () => {
  it('posts to the run endpoint with a tz and returns the message', async () => {
    post.mockResolvedValue({ message: { message_id: 'm1' } });
    const result = await runReport('r1');
    expect(result).toEqual({ message_id: 'm1' });
    const [path, body, options] = post.mock.calls[0];
    expect(path).toBe('/reports/r1/run');
    expect(body).toBeUndefined();
    expect('tz' in options.query).toBe(true);
  });
});

describe('previewReport', () => {
  it('posts to the preview endpoint with a tz and returns the sections', async () => {
    post.mockResolvedValue({ sections: [{ type: 'task_query', content: { items: [] } }] });
    const result = await previewReport('r1');
    expect(result).toEqual([{ type: 'task_query', content: { items: [] } }]);
    const [path, body, options] = post.mock.calls[0];
    expect(path).toBe('/reports/r1/preview');
    expect(body).toBeUndefined();
    expect('tz' in options.query).toBe(true);
  });
});

describe('deleteReport', () => {
  it('deletes the report path', async () => {
    del.mockResolvedValue({ message: 'deleted' });
    await deleteReport('r1');
    expect(del.mock.calls[0][0]).toBe('/reports/r1');
  });
});
