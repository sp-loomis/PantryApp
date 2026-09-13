/**
 * MessageLogPage — the in-app notification log.
 *
 * Lists generated messages (newest first), each rendered from its stored section
 * snapshots. Supports deep-linking: navigating to `/messages#<message_id>`
 * scrolls the matching message into view, highlights it, and marks it read.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Badge,
  Box,
  Center,
  Flex,
  Heading,
  HStack,
  IconButton,
  Spinner,
  Text,
  VStack,
} from '@chakra-ui/react';
import { listMessages, markRead, markUnread, deleteMessage } from '@pantry-app/shared';
import MessageSections from '../components/MessageSections';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import { TrashIcon } from '../components/icons';

function formatWhen(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function MessageLogPage() {
  const location = useLocation();
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [highlightId, setHighlightId] = useState(null);
  const scrolledTo = useRef(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setMessages(await listMessages());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Deep-link: once messages are loaded, scroll to the hash target, highlight it,
  // and mark it read. Guarded so it runs once per hash value.
  useEffect(() => {
    const targetId = location.hash ? location.hash.slice(1) : null;
    if (!targetId || loading || scrolledTo.current === targetId) return;
    const el = document.getElementById(targetId);
    if (!el) return;
    scrolledTo.current = targetId;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setHighlightId(targetId);
    const target = messages.find((m) => m.message_id === targetId);
    if (target && !target.read_at) {
      markRead(targetId)
        .then(() => load())
        .catch(() => {});
    }
  }, [location.hash, loading, messages, load]);

  const handleToggleRead = async (message) => {
    try {
      if (message.read_at) {
        await markUnread(message.message_id);
      } else {
        await markRead(message.message_id);
      }
      await load();
    } catch (err) {
      setError(err);
    }
  };

  const handleDelete = async (message) => {
    try {
      await deleteMessage(message.message_id);
      await load();
    } catch (err) {
      setError(err);
    }
  };

  return (
    <Box>
      <Text fontSize="2xl" fontWeight="bold" mb={4}>
        Messages
      </Text>

      <ErrorMessage error={error} />

      {loading ? (
        <Center py={12}>
          <Spinner color="brand.500" thickness="3px" />
        </Center>
      ) : messages.length === 0 ? (
        <EmptyState
          title="No messages yet"
          description="Reports you run or schedule will show up here."
        />
      ) : (
        <VStack spacing={4} align="stretch">
          {messages.map((message) => {
            const unread = !message.read_at;
            const highlighted = message.message_id === highlightId;
            return (
              <Box
                key={message.message_id}
                id={message.message_id}
                bg="white"
                borderWidth="1px"
                borderColor={highlighted ? 'brand.400' : 'gray.200'}
                boxShadow={highlighted ? 'md' : 'sm'}
                borderRadius="lg"
                p={4}
                scrollMarginTop="16px"
              >
                <Flex align="center" justify="space-between" mb={2} gap={2}>
                  <HStack spacing={2} minW={0}>
                    {unread && <Badge colorScheme="brand">New</Badge>}
                    <Heading size="sm" noOfLines={1}>
                      {message.title}
                    </Heading>
                  </HStack>
                  <HStack spacing={1} flexShrink={0}>
                    <Text
                      as="button"
                      fontSize="xs"
                      color="brand.600"
                      onClick={() => handleToggleRead(message)}
                    >
                      {unread ? 'Mark read' : 'Mark unread'}
                    </Text>
                    <IconButton
                      aria-label="Delete message"
                      icon={<TrashIcon />}
                      size="xs"
                      variant="ghost"
                      colorScheme="red"
                      onClick={() => handleDelete(message)}
                    />
                  </HStack>
                </Flex>
                <Text fontSize="xs" color="gray.400" mb={3}>
                  {formatWhen(message.created_at)}
                </Text>
                <MessageSections sections={message.sections} />
              </Box>
            );
          })}
        </VStack>
      )}
    </Box>
  );
}
