import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the HTTP layer so we exercise the service's envelope handling only.
const post = vi.fn();
const patch = vi.fn();
const del = vi.fn();
vi.mock('./apiClient.js', () => ({
  api: {
    post: (...args) => post(...args),
    patch: (...args) => patch(...args),
    del: (...args) => del(...args),
  },
}));

const { createItem, updateItemsBulk, deleteItemsBulk, addItemsTagsBulk } =
  await import('./inventoryService.js');

describe('createItem', () => {
  beforeEach(() => {
    post.mockReset();
  });

  it('returns a single item object for the default (single) create', async () => {
    post.mockResolvedValue({ item: { item_id: 'a', name: 'Milk' } });

    const result = await createItem({ name: 'Milk', location_id: 'fridge' });

    expect(Array.isArray(result)).toBe(false);
    expect(result.item_id).toBe('a');
    expect(post).toHaveBeenCalledWith('/items', { name: 'Milk', location_id: 'fridge' });
  });

  it('returns an array when the backend creates multiple copies', async () => {
    post.mockResolvedValue({
      items: [
        { item_id: 'a', name: 'Milk' },
        { item_id: 'b', name: 'Milk' },
        { item_id: 'c', name: 'Milk' },
      ],
    });

    const result = await createItem({ name: 'Milk', location_id: 'fridge', copies: 3 });

    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(3);
    expect(result.map((i) => i.item_id)).toEqual(['a', 'b', 'c']);
  });
});

describe('updateItemsBulk', () => {
  beforeEach(() => {
    patch.mockReset();
  });

  it('patches /items with the id list and updates', async () => {
    patch.mockResolvedValue({ updated: 2, skipped: [] });

    const result = await updateItemsBulk(['a', 'b'], { location_id: 'pantry' });

    expect(result).toEqual({ updated: 2, skipped: [] });
    expect(patch.mock.calls[0][0]).toBe('/items');
    expect(patch.mock.calls[0][1]).toEqual({
      item_ids: ['a', 'b'],
      updates: { location_id: 'pantry' },
    });
  });
});

describe('deleteItemsBulk', () => {
  beforeEach(() => {
    del.mockReset();
  });

  it('sends the id list as the delete body', async () => {
    del.mockResolvedValue({ deleted: 2, skipped: [] });

    const result = await deleteItemsBulk(['a', 'b']);

    expect(result).toEqual({ deleted: 2, skipped: [] });
    expect(del.mock.calls[0][0]).toBe('/items');
    expect(del.mock.calls[0][1]).toEqual({ body: { item_ids: ['a', 'b'] } });
  });
});

describe('addItemsTagsBulk', () => {
  beforeEach(() => {
    post.mockReset();
  });

  it('posts the id list and tags to the bulk tag endpoint', async () => {
    post.mockResolvedValue({ updated: 2, skipped: [] });

    const result = await addItemsTagsBulk(['a', 'b'], ['fresh', 'snack']);

    expect(result).toEqual({ updated: 2, skipped: [] });
    expect(post.mock.calls[0][0]).toBe('/items/tags');
    expect(post.mock.calls[0][1]).toEqual({
      item_ids: ['a', 'b'],
      tags: ['fresh', 'snack'],
    });
  });
});
