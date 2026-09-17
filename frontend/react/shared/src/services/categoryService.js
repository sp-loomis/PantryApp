/**
 * Category service
 *
 * One function per backend endpoint (mirrors the locations service). Each unwraps
 * the single-key response envelope so callers get the useful value directly.
 * Platform-agnostic — usable from web and future mobile.
 *
 * A category declares a `measure_type` (`count` | `weight` | `volume`) and, for
 * weight/volume, a `preferred_unit` (the reporting/conversion target). Items
 * assigned to a category must carry a dimension of that measure type.
 */

import { api } from './apiClient.js';

export async function listCategories() {
  const data = await api.get('/categories');
  return data.categories;
}

export async function getCategory(categoryId) {
  const data = await api.get(`/categories/${categoryId}`);
  return data.category;
}

export async function createCategory({ name, measure_type, preferred_unit, description = '' }) {
  const data = await api.post('/categories', { name, measure_type, preferred_unit, description });
  return data.category;
}

export async function updateCategory(categoryId, updates) {
  const data = await api.put(`/categories/${categoryId}`, updates);
  return data.category;
}

export async function deleteCategory(categoryId) {
  return api.del(`/categories/${categoryId}`);
}

/**
 * Valid units per measure type, e.g. `{ count: [], weight: ["g", ...], volume: [...] }`.
 * Drives the category form's unit select.
 */
export async function listMeasureUnits() {
  const data = await api.get('/categories/units');
  return data.units;
}
