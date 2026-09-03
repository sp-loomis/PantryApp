/**
 * Auth token provider
 *
 * Supplies the Bearer token the API client attaches to every backend request.
 * This is the single seam that lets the same fetch code run against a local
 * dev shim (static token) or a real Cognito-backed API (Amplify session).
 */

import { fetchAuthSession } from 'aws-amplify/auth';
import { getAuthMode } from '../config/env.js';

// Sent in local mode; the local backend shim ignores the token and injects a
// fixed dev user, so any non-empty value works.
const LOCAL_DEV_TOKEN = 'local-dev-token';

/**
 * Resolve the JWT to send as `Authorization: Bearer <token>`.
 * @returns {Promise<string|null>} the token, or null if unavailable.
 */
export async function getAuthToken() {
  if (getAuthMode() === 'local') {
    return LOCAL_DEV_TOKEN;
  }

  // Cognito mode: the backend authorizer validates the ID token (see
  // AUTHENTICATION.md). Amplify refreshes it automatically, so fetch per-request.
  const { tokens } = await fetchAuthSession();
  return tokens?.idToken?.toString() ?? null;
}
