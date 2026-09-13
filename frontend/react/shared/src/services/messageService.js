/**
 * Message service
 *
 * One function per backend endpoint for the notification/message log. Each
 * unwraps the single-key response envelope. Unread state is tracked server-side
 * via a sparse index; `listUnread` returns both the messages and their count for
 * the toolbar badge.
 *
 * Platform-agnostic — usable from web and future mobile.
 */

import { api } from './apiClient.js';

/** List all messages, newest first. */
export async function listMessages() {
  const data = await api.get('/messages');
  return data.messages;
}

/**
 * List unread messages plus the unread count.
 * @returns {Promise<{messages: Array, unread_count: number}>}
 */
export async function listUnread() {
  const data = await api.get('/messages/unread');
  return { messages: data.messages, unread_count: data.unread_count };
}

export async function getMessage(messageId) {
  const data = await api.get(`/messages/${messageId}`);
  return data.message;
}

export async function markRead(messageId) {
  const data = await api.post(`/messages/${messageId}/read`);
  return data.message;
}

export async function markUnread(messageId) {
  const data = await api.post(`/messages/${messageId}/unread`);
  return data.message;
}

export async function deleteMessage(messageId) {
  return api.del(`/messages/${messageId}`);
}
