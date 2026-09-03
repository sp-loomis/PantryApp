import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the HTTP layer so we exercise the service's envelope handling only.
const post = vi.fn();
vi.mock('./apiClient.js', () => ({
  api: { post: (...args) => post(...args) },
}));

const { createItem } = await import('./inventoryService.js');

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
