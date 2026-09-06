/**
 * TasksDashboardPage — the task home.
 *
 * Shows everything that needs doing now, grouped by urgency
 * (Overdue · Today · This week · Upcoming). Checking a task off completes it for
 * the current window; recurring chores reappear next window, and a completed
 * one-shot offers an Undo. Recurring tasks completed for the current window are
 * tucked into a "Completed" section so they can be un-checked.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Button,
  Center,
  Flex,
  Heading,
  HStack,
  Spinner,
  Text,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { listTasks, completeTask, uncompleteTask } from '@pantry-app/shared';
import TaskCard from '../components/TaskCard';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import { PlusIcon } from '../components/icons';
import { groupActiveTasks } from '../utils/taskStatus';

export default function TasksDashboardPage() {
  const toast = useToast();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [togglingId, setTogglingId] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      // Fetch everything so we can show active tasks *and* offer undo for tasks
      // completed in the current window.
      setTasks(await listTasks({ status: 'all' }));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleToggle = async (task) => {
    setTogglingId(task.task_id);
    try {
      if (task.done) {
        await uncompleteTask(task.task_id);
      } else {
        await completeTask(task.task_id);
        // A one-shot vanishes from the board once done, so surface an undo path.
        if (task.recurrence_type === 'none') {
          toast({
            title: `Completed “${task.name}”`,
            status: 'success',
            duration: 5000,
            isClosable: true,
          });
        }
      }
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setTogglingId(null);
    }
  };

  const active = tasks.filter((t) => t.active);
  const groups = groupActiveTasks(active);
  // Recurring tasks done for the current window — a bounded set that resets, so
  // safe to list for un-checking without the historical buildup we avoid.
  const completedThisWindow = tasks.filter((t) => t.done && t.recurrence_type !== 'none');

  return (
    <Box>
      <Flex align="center" justify="space-between" mb={4} gap={3}>
        <Text fontSize="2xl" fontWeight="bold">
          Tasks
        </Text>
        <Button as={RouterLink} to="/tasks/new" leftIcon={<PlusIcon boxSize={4} />}>
          Add task
        </Button>
      </Flex>

      <ErrorMessage error={error} />

      {loading ? (
        <Center py={12}>
          <Spinner color="brand.500" thickness="3px" />
        </Center>
      ) : active.length === 0 && completedThisWindow.length === 0 ? (
        <EmptyState
          title="Nothing on the list"
          description="Add a chore or a one-off task to get started."
          action={
            <Button as={RouterLink} to="/tasks/new" mt={2}>
              Add task
            </Button>
          }
        />
      ) : (
        <VStack spacing={6} align="stretch">
          {active.length === 0 ? (
            <Text color="gray.500">All caught up for now. 🎉</Text>
          ) : (
            groups.map((group) => (
              <Box key={group.key}>
                <Heading size="xs" textTransform="uppercase" color="gray.400" mb={2}>
                  {group.title}
                </Heading>
                <VStack spacing={3} align="stretch">
                  {group.tasks.map((task) => (
                    <TaskCard
                      key={task.task_id}
                      task={task}
                      onToggleComplete={handleToggle}
                      isToggling={togglingId === task.task_id}
                    />
                  ))}
                </VStack>
              </Box>
            ))
          )}

          {completedThisWindow.length > 0 && (
            <Box>
              <HStack mb={2}>
                <Heading size="xs" textTransform="uppercase" color="gray.400">
                  Completed
                </Heading>
                <Text fontSize="xs" color="gray.400">
                  ({completedThisWindow.length})
                </Text>
              </HStack>
              <VStack spacing={3} align="stretch">
                {completedThisWindow.map((task) => (
                  <TaskCard
                    key={task.task_id}
                    task={task}
                    onToggleComplete={handleToggle}
                    isToggling={togglingId === task.task_id}
                  />
                ))}
              </VStack>
            </Box>
          )}
        </VStack>
      )}
    </Box>
  );
}
