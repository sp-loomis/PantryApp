/**
 * Slack integration service
 *
 * One function per backend connections endpoint (see
 * docs/slack-integration-plan.md §6). Each unwraps the single-key response
 * envelope. No function ever receives the bot token — the API never returns it.
 *
 * OAuth is a full-page browser redirect, not a fetch: `getAuthorizeUrl` returns
 * the Slack authorize URL (an authenticated call), and the caller navigates to
 * it with `window.location`. The callback is handled entirely server-side.
 *
 * Platform-agnostic — usable from web and future mobile.
 */

import { api } from './apiClient.js';

/** Get the Slack authorize URL to redirect the browser to (starts OAuth). */
export async function getAuthorizeUrl() {
  const data = await api.get('/slack/oauth/start');
  return data.authorize_url;
}

/** List the user's connected workspaces (never includes the bot token). */
export async function listConnections() {
  const data = await api.get('/slack/connections');
  return data.connections;
}

/** List channels available to a connection, for the picker. */
export async function listChannels(connectionId) {
  const data = await api.get(`/slack/connections/${connectionId}/channels`);
  return data.channels;
}

/** Revoke + delete a connection. */
export async function disconnect(connectionId) {
  return api.del(`/slack/connections/${connectionId}`);
}

/** Post a "connection works" message to a chosen channel. */
export async function testConnection(connectionId, channelId) {
  return api.post(`/slack/connections/${connectionId}/test`, { channel_id: channelId });
}

/**
 * LOCAL DEV ONLY: create a fake connection without real Slack OAuth.
 * The endpoint returns 404 outside the local tier.
 */
export async function devStubConnect(teamName = 'Local Dev Workspace') {
  const data = await api.post('/slack/connections/dev-stub', { team_name: teamName });
  return data.connection;
}
