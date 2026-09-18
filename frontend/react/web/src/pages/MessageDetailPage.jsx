/**
 * MessageDetailPage — one report/message on its own page, with interactive
 * task check-off.
 *
 * Unlike the static message log (`MessageLogPage`), the task rows here are
 * checkboxes that complete/uncomplete the underlying task. The message's task
 * snapshots are frozen, but on load we overlay the *live* task state
 * (`listTasks`) so checkboxes read true even if a task changed after the report
 * ran. Membership (which tasks the report listed) stays frozen. Web-only —
 * Slack delivery stays static.
 */

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Center, Spinner, Text } from '@chakra-ui/react';
import {
  getMessage,
  listTasks,
  markRead,
  completeTask,
  uncompleteTask,
} from '@pantry-app/shared';
import PageHeader from '../components/PageHeader';
import MessageSections from '../components/MessageSections';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import { buildTaskState } from '../utils/reportTasks';

function formatWhen(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function MessageDetailPage() {
  const { messageId } = useParams();
  const [message, setMessage] = useState(null);
  const [taskState, setTaskState] = useState(() => new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [togglingId, setTogglingId] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setNotFound(false);
      // Fetch the frozen message and the live task list together, then reconcile.
      const [msg, tasks] = await Promise.all([getMessage(messageId), listTasks({ status: 'all' })]);
      setMessage(msg);
      setTaskState(buildTaskState(tasks));
      // Mark read on view, mirroring the message log's deep-link behavior.
      if (!msg.read_at) markRead(messageId).catch(() => {});
    } catch (err) {
      if (err?.status === 404) setNotFound(true);
      else setError(err);
    } finally {
      setLoading(false);
    }
  }, [messageId]);

  useEffect(() => {
    load();
  }, [load]);

  // Toggle the live task behind a report row. Optimistic; reconciles to the
  // task returned by the API, reverts on failure.
  const handleToggleTask = useCallback(
    async (row) => {
      const id = row.task_id;
      const prev = taskState.get(id);
      if (!prev) return; // deleted task — checkbox is disabled, shouldn't fire
      setTogglingId(id);
      setError(null);
      // Optimistic flip.
      setTaskState((s) => {
        const next = new Map(s);
        next.set(id, { ...prev, done: !prev.done });
        return next;
      });
      try {
        const updated = prev.done ? await uncompleteTask(id) : await completeTask(id);
        setTaskState((s) => {
          const next = new Map(s);
          next.set(id, updated);
          return next;
        });
      } catch (err) {
        // Revert to the pre-toggle task on failure.
        setTaskState((s) => {
          const next = new Map(s);
          next.set(id, prev);
          return next;
        });
        setError(err);
      } finally {
        setTogglingId(null);
      }
    },
    [taskState],
  );

  if (loading) {
    return (
      <Center py={12}>
        <Spinner color="brand.500" thickness="3px" />
      </Center>
    );
  }

  if (notFound) {
    return (
      <Box>
        <PageHeader title="Message" back="/messages" />
        <EmptyState
          title="Message not found"
          description="It may have been deleted. Head back to the message log."
        />
      </Box>
    );
  }

  if (error && !message) {
    return (
      <Box>
        <PageHeader title="Message" back="/messages" />
        <ErrorMessage error={error} />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title={message.title} back="/messages" />
      <Text fontSize="xs" color="gray.400" mb={4}>
        {formatWhen(message.created_at)}
      </Text>

      <ErrorMessage error={error} />

      <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="lg" p={4}>
        <MessageSections
          sections={message.sections}
          interactive
          taskState={taskState}
          onToggleTask={handleToggleTask}
          togglingId={togglingId}
        />
      </Box>
    </Box>
  );
}
