/**
 * MessageLogPage — the in-app notification log.
 *
 * Lists generated messages (newest first), each rendered from its stored section
 * snapshots. Supports deep-linking: navigating to `/messages#<message_id>`
 * scrolls the matching message into view, highlights it, and marks it read.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Badge,
  Box,
  Button,
  Center,
  Flex,
  Heading,
  HStack,
  IconButton,
  Select,
  Spinner,
  Text,
  useDisclosure,
  VStack,
  Wrap,
  WrapItem,
} from '@chakra-ui/react';
import {
  listMessages,
  markRead,
  markUnread,
  deleteMessage,
  markAllRead,
  deleteMessages,
} from '@pantry-app/shared';
import MessageSections from '../components/MessageSections';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import ConfirmDialog from '../components/ConfirmDialog';
import { TrashIcon } from '../components/icons';

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'unread', label: 'Unread' },
  { value: 'read', label: 'Read' },
];

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
  const [filter, setFilter] = useState('all');
  const [bulkBusy, setBulkBusy] = useState(false);
  const scrolledTo = useRef(null);
  const confirmDelete = useDisclosure();

  // The set currently shown; bulk actions operate on exactly this view.
  const visible = useMemo(() => {
    if (filter === 'unread') return messages.filter((m) => !m.read_at);
    if (filter === 'read') return messages.filter((m) => m.read_at);
    return messages;
  }, [messages, filter]);

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

  // Bulk actions target the currently filtered view only.
  const unreadInView = visible.filter((m) => !m.read_at);

  const handleMarkAllRead = async () => {
    if (unreadInView.length === 0) return;
    try {
      setBulkBusy(true);
      await markAllRead(unreadInView.map((m) => m.message_id));
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBulkBusy(false);
    }
  };

  const handleDeleteAll = async () => {
    try {
      setBulkBusy(true);
      await deleteMessages(visible.map((m) => m.message_id));
      confirmDelete.onClose();
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBulkBusy(false);
    }
  };

  const filterLabel = FILTERS.find((f) => f.value === filter)?.label.toLowerCase();

  return (
    <Box>
      <Text fontSize="2xl" fontWeight="bold" mb={4}>
        Messages
      </Text>

      {messages.length > 0 && (
        <Wrap spacing={3} align="center" mb={4}>
          <WrapItem>
            <Select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              bg="white"
              w="150px"
              size="sm"
            >
              {FILTERS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </Select>
          </WrapItem>
          <WrapItem>
            <Button
              size="sm"
              variant="outline"
              onClick={handleMarkAllRead}
              isDisabled={unreadInView.length === 0 || bulkBusy}
            >
              Mark all read
            </Button>
          </WrapItem>
          <WrapItem>
            <Button
              size="sm"
              variant="outline"
              colorScheme="red"
              onClick={confirmDelete.onOpen}
              isDisabled={visible.length === 0 || bulkBusy}
            >
              Delete all
            </Button>
          </WrapItem>
        </Wrap>
      )}

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
      ) : visible.length === 0 ? (
        <EmptyState
          title={`No ${filterLabel} messages`}
          description="Try a different filter."
        />
      ) : (
        <VStack spacing={4} align="stretch">
          {visible.map((message) => {
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

      <ConfirmDialog
        isOpen={confirmDelete.isOpen}
        onClose={confirmDelete.onClose}
        onConfirm={handleDeleteAll}
        isLoading={bulkBusy}
        title="Delete messages"
        body={
          filter === 'all'
            ? `Delete all ${visible.length} messages? This can't be undone.`
            : `Delete the ${visible.length} ${filterLabel} ${
                visible.length === 1 ? 'message' : 'messages'
              } shown? This can't be undone.`
        }
        confirmLabel="Delete all"
      />
    </Box>
  );
}
