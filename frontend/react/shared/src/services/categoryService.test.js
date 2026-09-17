import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the HTTP layer so we exercise the service's envelope handling only.
const get = vi.fn();
const post = vi.fn();
vi.mock('./apiClient.js', () => ({
  api: {
    get: (...args) => get(...args),
    post: (...args) => post(...args),
  },
}));

const { listCategories, createCategory, listMeasureUnits } = await import('./categoryService.js');

describe('categoryService', () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
  });

  it('listCategories unwraps the categories envelope', async () => {
    get.mockResolvedValue({ categories: [{ category_id: 'c1', name: 'Beef' }] });
    const result = await listCategories();
    expect(result).toEqual([{ category_id: 'c1', name: 'Beef' }]);
    expect(get).toHaveBeenCalledWith('/categories');
  });

  it('createCategory posts the measure fields and unwraps the category', async () => {
    post.mockResolvedValue({ category: { category_id: 'c1', name: 'Beef' } });
    const result = await createCategory({
      name: 'Beef', measure_type: 'weight', preferred_unit: 'lb',
    });
    expect(result.category_id).toBe('c1');
    expect(post).toHaveBeenCalledWith('/categories', {
      name: 'Beef', measure_type: 'weight', preferred_unit: 'lb', description: '',
    });
  });

  it('listMeasureUnits unwraps the units catalog', async () => {
    get.mockResolvedValue({ units: { count: [], weight: ['lb'], volume: ['l'] } });
    const result = await listMeasureUnits();
    expect(result.weight).toContain('lb');
    expect(get).toHaveBeenCalledWith('/categories/units');
  });
});
