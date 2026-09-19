/**
 * MessageDetailPage — one report/message on its own page, with interactive
 * task check-off.
 *
 * Unlike the static message log (`MessageLogPage`), the task rows here are
 * interactive: a checkbox for a plain task, a Yes/No pair for a decision task.
 * We overlay the *live* task state (`listTasks`) so rows read true even if a
 * task changed after the report ran.
 *
 * Decision paths: answering a decision can activate a new round of dependent
 * tasks. When the message came from a report (`report_id`), we re-render that
 * report live (`previewReport`) after each answer so the next round appears in
 * place — membership is no longer frozen. A manual message with no report_id
 * keeps the frozen snapshot and only overlays live per-task state. Web-only —
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
  previewReport,
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

  // After a mutation, re-render the source report (if any) so a newly answered
  // decision reveals/hides its dependent tasks, and refresh live task state.
  // A manual message (no report_id) keeps its frozen membership.
  const refreshRound = useCallback(async () => {
    const reportId = message?.report_id;
    const [sections, tasks] = await Promise.all([
      reportId ? previewReport(reportId).catch(() => null) : Promise.resolve(null),
      listTasks({ status: 'all' }),
    ]);
    setTaskState(buildTaskState(tasks));
    if (sections) setMessage((m) => (m ? { ...m, sections } : m));
  }, [message?.report_id]);

  // Run a task mutation optimistically, reconcile, then refresh the round.
  const runMutation = useCallback(
    async (id, optimistic, mutate) => {
      const prev = taskState.get(id);
      if (!prev) return; // deleted task — control is disabled, shouldn't fire
      setTogglingId(id);
      setError(null);
      setTaskState((s) => new Map(s).set(id, { ...prev, ...optimistic }));
      try {
        const updated = await mutate();
        setTaskState((s) => new Map(s).set(id, updated));
        await refreshRound();
      } catch (err) {
        setTaskState((s) => new Map(s).set(id, prev)); // revert
        setError(err);
      } finally {
        setTogglingId(null);
      }
    },
    [taskState, refreshRound],
  );

  // Checkbox row: toggle completion.
  const handleToggleTask = useCallback(
    (row) => {
      const prev = taskState.get(row.task_id);
      if (!prev) return;
      return runMutation(
        row.task_id,
        { done: !prev.done },
        () => (prev.done ? uncompleteTask(row.task_id) : completeTask(row.task_id)),
      );
    },
    [taskState, runMutation],
  );

  // Decision row: answer Yes/No (clicking the current answer clears it).
  const handleAnswerTask = useCallback(
    (row, decision) => {
      const prev = taskState.get(row.task_id);
      if (!prev) return;
      const clearing = prev.last_decision === decision && prev.done;
      return runMutation(
        row.task_id,
        clearing ? { done: false, last_decision: null } : { done: true, last_decision: decision },
        () => (clearing ? uncompleteTask(row.task_id) : completeTask(row.task_id, decision)),
      );
    },
    [taskState, runMutation],
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
          onAnswerTask={handleAnswerTask}
          togglingId={togglingId}
        />
      </Box>
    </Box>
  );
}
