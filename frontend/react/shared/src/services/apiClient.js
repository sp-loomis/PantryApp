/**
 * API client
 *
 * Thin fetch wrapper for the Pantry backend. Resolves the base URL from env,
 * attaches the Bearer token, parses the JSON envelope, and normalizes errors:
 * the backend always returns `{ "error": "<message>" }` with a proper status
 * code, which becomes an `ApiError`.
 */

import { getApiBaseUrl } from '../config/env.js';
import { getAuthToken } from './authTokens.js';

/** Error thrown for any non-2xx backend response. */
export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/** Build a query string from an object, dropping empty/undefined/null values. */
function buildQuery(query) {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      params.append(key, value);
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

/**
 * Perform an authenticated request.
 * @param {string} method HTTP method.
 * @param {string} path   Path beginning with '/', e.g. '/items'.
 * @param {{body?: any, query?: Object}} [options]
 * @returns {Promise<any>} parsed JSON body.
 * @throws {ApiError} on non-2xx.
 */
export async function request(method, path, { body, query } = {}) {
  const url = `${getApiBaseUrl()}${path}${buildQuery(query)}`;
  const headers = { 'Content-Type': 'application/json' };

  const token = await getAuthToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text };
    }
  }

  if (!response.ok) {
    const message = data?.error || `Request failed (${response.status})`;
    throw new ApiError(message, response.status, data);
  }

  return data;
}

/** Convenience verbs. */
export const api = {
  get: (path, options) => request('GET', path, options),
  post: (path, body, options) => request('POST', path, { ...options, body }),
  put: (path, body, options) => request('PUT', path, { ...options, body }),
  del: (path, options) => request('DELETE', path, options),
};
