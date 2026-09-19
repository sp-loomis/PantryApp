/**
 * TaskDetailPage — full detail for one task, with complete/edit/delete.
 */

import { useEffect, useState, useCallback } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardBody,
  Center,
  Divider,
  Flex,
  HStack,
  IconButton,
  Spinner,
  Tag,
  Text,
  VStack,
  Wrap,
  WrapItem,
  Badge,
  useDisclosure,
} from '@chakra-ui/react';
import { getTask, deleteTask, completeTask, uncompleteTask } from '@pantry-app/shared';
import DecisionButtons from '../components/DecisionButtons';
import PageHeader from '../components/PageHeader';
import ErrorMessage from '../components/ErrorMessage';
import ConfirmDialog from '../components/ConfirmDialog';
import { EditIcon, TrashIcon } from '../components/icons';
import { formatDate } from '../utils/dates';
import { taskStatusBadge, recurrenceLabel } from '../utils/taskStatus';

function Field({ label, children }) {
  return (
    <Box>
      <Text fontSize="xs" textTransform="uppercase" color="gray.400" fontWeight="semibold" mb={1}>
        {label}
      </Text>
      {children}
    </Box>
  );
}

export default function TaskDetailPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const { isOpen, onOpen, onClose } = useDisclosure();

  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [toggling, setToggling] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setTask(await getTask(taskId));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleToggle = async () => {
    try {
      setToggling(true);
      const updated = task.done ? await uncompleteTask(taskId) : await completeTask(taskId);
      setTask(updated);
    } catch (err) {
      setError(err);
    } finally {
      setToggling(false);
    }
  };

  // Answer a decision task Yes/No (clicking the current answer clears it).
  const handleAnswer = async (decision) => {
    try {
      setToggling(true);
      const clearing = task.done && task.last_decision === decision;
      const updated = clearing
        ? await uncompleteTask(taskId)
        : await completeTask(taskId, decision);
      setTask(updated);
    } catch (err) {
      setError(err);
    } finally {
      setToggling(false);
    }
  };

  const handleDelete = async () => {
    try {
      setDeleting(true);
      await deleteTask(taskId);
      navigate('/tasks');
    } catch (err) {
      setError(err);
      setDeleting(false);
      onClose();
    }
  };

  if (loading) {
    return (
      <Center py={12}>
        <Spinner color="brand.500" thickness="3px" />
      </Center>
    );
  }

  if (error && !task) {
    return (
      <Box>
        <PageHeader title="Task" back />
        <ErrorMessage error={error} />
      </Box>
    );
  }

  const badge = taskStatusBadge(task);

  return (
    <Box>
      <PageHeader
        title={task.name}
        back
        actions={
          <HStack>
            <IconButton
              as={RouterLink}
              to={`/tasks/${taskId}/edit`}
              aria-label="Edit task"
              icon={<EditIcon boxSize={5} />}
              variant="ghost"
              colorScheme="gray"
            />
            <IconButton
              aria-label="Delete task"
              icon={<TrashIcon boxSize={5} />}
              variant="ghost"
              colorScheme="red"
              onClick={onOpen}
            />
          </HStack>
        }
      />

      <ErrorMessage error={error} />

      <Card variant="outline">
        <CardBody>
          <VStack align="stretch" spacing={4}>
            <Field label="Status">
              <Badge colorScheme={badge.color}>{badge.label}</Badge>
            </Field>

            <Field label="Repeat">
              <Text>{recurrenceLabel(task)}</Text>
            </Field>

            {task.recurrence_type === 'none' && (
              <Field label="Due date">
                <Text>{task.due_date ? formatDate(task.due_date) : '—'}</Text>
              </Field>
            )}

            {task.recurrence_type !== 'none' && task.current_due && (
              <Field label="Due this window">
                <Text>{formatDate(task.current_due)}</Text>
              </Field>
            )}

            <Field label="Tags">
              {task.tags?.length > 0 ? (
                <Wrap spacing={2}>
                  {task.tags.map((tag) => (
                    <WrapItem key={tag}>
                      <Tag colorScheme="brand" variant="subtle">
                        {tag}
                      </Tag>
                    </WrapItem>
                  ))}
                </Wrap>
              ) : (
                <Text>—</Text>
              )}
            </Field>

            {task.notes && (
              <>
                <Divider />
                <Field label="Notes">
                  <Text whiteSpace="pre-wrap">{task.notes}</Text>
                </Field>
              </>
            )}
          </VStack>
        </CardBody>
      </Card>

      <Flex mt={4} gap={3} direction={{ base: 'column', md: 'row' }}>
        {task.answer_mode === 'yesno' ? (
          <DecisionButtons
            decision={task.last_decision}
            isDisabled={toggling}
            onAnswer={handleAnswer}
            name={task.name}
            size="md"
          />
        ) : (
          <Button
            onClick={handleToggle}
            isLoading={toggling}
            colorScheme={task.done ? 'gray' : 'brand'}
            variant={task.done ? 'outline' : 'solid'}
            width={{ base: 'full', md: 'auto' }}
          >
            {task.done ? 'Mark not done' : 'Mark done'}
          </Button>
        )}
        <Button
          as={RouterLink}
          to={`/tasks/${taskId}/edit`}
          variant="outline"
          width={{ base: 'full', md: 'auto' }}
        >
          Edit task
        </Button>
      </Flex>

      <ConfirmDialog
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={handleDelete}
        isLoading={deleting}
        title="Delete task"
        body={`Delete "${task.name}"? This cannot be undone.`}
      />
    </Box>
  );
}
