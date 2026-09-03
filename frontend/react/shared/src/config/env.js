/**
 * Environment configuration
 *
 * Reads Vite-injected env vars. These two vars are the only seam between the
 * three deployment tiers (see frontend/react/DESIGN.md): the same code talks to
 * a local shim, a remote dev backend, or prod purely by changing them.
 */

/** Safe accessor for import.meta.env (undefined under non-Vite runtimes like vitest). */
function env(key) {
  try {
    return import.meta.env?.[key];
  } catch {
    return undefined;
  }
}

/** Base URL of the backend HTTP API, trailing slash stripped. */
export function getApiBaseUrl() {
  return (env('VITE_API_GATEWAY_URL') || '').replace(/\/+$/, '');
}

/**
 * Auth mode: 'local' (dev-bypass stub, no Cognito) or 'cognito' (real Amplify).
 * Defaults to 'cognito' so deployed tiers require a real session.
 */
export function getAuthMode() {
  return env('VITE_AUTH_MODE') === 'local' ? 'local' : 'cognito';
}

/** The stubbed user used in local auth mode (mirrors the backend's DEV_USER_ID). */
export const LOCAL_DEV_USER = { userId: 'dev-user', email: 'dev@local' };
