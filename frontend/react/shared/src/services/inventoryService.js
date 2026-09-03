/**
 * Inventory service
 *
 * One function per backend endpoint. Each unwraps the single-key response
 * envelope so callers get the useful value directly (e.g. an array of items).
 * Platform-agnostic — usable from web and future mobile.
 */

import { api } from './apiClient.js';

// ---------------------------------------------------------------------------
// Locations
// ---------------------------------------------------------------------------

export async function listLocations() {
  const data = await api.get('/locations');
  return data.locations;
}

export async function getLocation(locationId) {
  const data = await api.get(`/locations/${locationId}`);
  return data.location;
}

export async function createLocation({ name, description = '' }) {
  const data = await api.post('/locations', { name, description });
  return data.location;
}

export async function updateLocation(locationId, updates) {
  const data = await api.put(`/locations/${locationId}`, updates);
  return data.location;
}

export async function deleteLocation(locationId) {
  return api.del(`/locations/${locationId}`);
}

// ---------------------------------------------------------------------------
// Items
// ---------------------------------------------------------------------------

export async function listItems({ location_id, tag } = {}) {
  const data = await api.get('/items', { query: { location_id, tag } });
  return data.items;
}

export async function getItem(itemId) {
  const data = await api.get(`/items/${itemId}`);
  return data.item;
}

/**
 * Create an item.
 * @param {{name, location_id, dimensions?, use_by_date?, tags?, notes?}} payload
 */
export async function createItem(payload) {
  const data = await api.post('/items', payload);
  return data.item;
}

export async function updateItem(itemId, updates) {
  const data = await api.put(`/items/${itemId}`, updates);
  return data.item;
}

export async function deleteItem(itemId) {
  return api.del(`/items/${itemId}`);
}

// ---------------------------------------------------------------------------
// Item tags
// ---------------------------------------------------------------------------

export async function getItemTags(itemId) {
  const data = await api.get(`/items/${itemId}/tags`);
  return data.tags;
}

export async function addItemTags(itemId, tags) {
  const data = await api.post(`/items/${itemId}/tags`, { tags });
  return data.tags;
}

export async function removeItemTag(itemId, tag) {
  const data = await api.del(`/items/${itemId}/tags/${encodeURIComponent(tag)}`);
  return data.tags;
}

// ---------------------------------------------------------------------------
// Tags (all) & Search
// ---------------------------------------------------------------------------

export async function listTags() {
  const data = await api.get('/tags');
  return data.tags;
}

/**
 * Fuzzy search.
 * @param {{name?, location_id?, tags?, use_by_date_start?, use_by_date_end?, min_score?}} criteria
 * @returns items; when `name` is given each item carries a `match` object.
 */
export async function searchItems(criteria = {}) {
  const data = await api.post('/search', criteria);
  return data.items;
}
