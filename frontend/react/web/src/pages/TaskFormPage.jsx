/**
 * TaskFormPage — create or edit a task.
 *
 * One component for both modes (keyed on the :taskId param). Uses controlled
 * state because of the custom RecurrenceField and TagInput controls.
 */

import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Center,
  Checkbox,
  FormControl,
  FormHelperText,
  FormLabel,
  Input,
  Spinner,
  Textarea,
  VStack,
  Text,
} from '@chakra-ui/react';
import {
  getTask,
  createTask,
  updateTask,
  listTasks,
  validateTaskName,
  validateRecurrence,
} from '@pantry-app/shared';
import PageHeader from '../components/PageHeader';
import ErrorMessage from '../components/ErrorMessage';
import RecurrenceField from '../components/RecurrenceField';
import TagInput from '../components/TagInput';
import TaskTriggerBuilder from '../components/TaskTriggerBuilder';

const EMPTY_RECURRENCE = { recurrence_type: 'none', recurrence_interval: 2, anchor_date: '' };

export default function TaskFormPage() {
  const { taskId } = useParams();
  const isEdit = Boolean(taskId);
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [notes, setNotes] = useState('');
  const [tags, setTags] = useState([]);
  const [recurrence, setRecurrence] = useState({ ...EMPTY_RECURRENCE });
  const [dueDate, setDueDate] = useState('');
  const [graceful, setGraceful] = useState(true);
  const [answerMode, setAnswerMode] = useState('checkbox');
  const [trigger, setTrigger] = useState(null);
  const [candidates, setCandidates] = useState([]);

  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(isEdit);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const isOneShot = recurrence.recurrence_type === 'none';
  const hasTrigger = Boolean(trigger?.source_task_id);

  // Candidate source tasks for the trigger builder (everything but this task).
  useEffect(() => {
    listTasks({ status: 'all' })
      .then((all) => setCandidates(all.filter((t) => t.task_id !== taskId)))
      .catch(() => setCandidates([]));
  }, [taskId]);

  const loadExisting = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const task = await getTask(taskId);
      setName(task.name);
      setNotes(task.notes || '');
      setTags(task.tags || []);
      setRecurrence({
        recurrence_type: task.recurrence_type || 'none',
        recurrence_interval: task.recurrence_interval ?? 2,
        anchor_date: task.anchor_date ? task.anchor_date.slice(0, 10) : '',
      });
      setDueDate(task.due_date ? task.due_date.slice(0, 10) : '');
      setGraceful(task.graceful ?? true);
      setAnswerMode(task.answer_mode || 'checkbox');
      setTrigger(task.trigger || null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    if (isEdit) loadExisting();
  }, [isEdit, loadExisting]);

  const validate = () => {
    const errors = {};
    const nameErr = validateTaskName(name);
    if (nameErr) errors.name = nameErr;
    const recErr = validateRecurrence(recurrence);
    if (recErr) errors.recurrence = recErr;
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    const payload = {
      name: name.trim(),
      notes,
      tags,
      recurrence_type: recurrence.recurrence_type,
      graceful,
      answer_mode: answerMode,
      // null clears any existing trigger (edit); an incomplete builder is treated as none.
      trigger: hasTrigger ? trigger : null,
    };
    if (recurrence.recurrence_type === 'interval') {
      payload.recurrence_interval = recurrence.recurrence_interval;
      payload.anchor_date = recurrence.anchor_date || null;
    }
    // A due date only applies to a one-shot task without a trigger; a triggered
    // task derives its due date from the source's decision.
    payload.due_date = isOneShot && !hasTrigger ? dueDate || null : null;

    try {
      setSubmitting(true);
      setError(null);
      const saved = isEdit ? await updateTask(taskId, payload) : await createTask(payload);
      navigate(isEdit ? `/tasks/${taskId}` : `/tasks/${saved.task_id}`);
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Center py={12}>
        <Spinner color="brand.500" thickness="3px" />
      </Center>
    );
  }

  return (
    <Box>
      <PageHeader title={isEdit ? 'Edit task' : 'New task'} back />
      <ErrorMessage error={error} />

      <form onSubmit={handleSubmit}>
        <VStack spacing={4} align="stretch" maxW="480px">
          <FormControl isInvalid={!!fieldErrors.name} isRequired>
            <FormLabel>Name</FormLabel>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Water the garden"
              autoFocus
            />
            {fieldErrors.name && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {fieldErrors.name}
              </Text>
            )}
          </FormControl>

          <Box>
            <RecurrenceField value={recurrence} onChange={setRecurrence} />
            {fieldErrors.recurrence && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {fieldErrors.recurrence}
              </Text>
            )}
          </Box>

          <FormControl>
            <Checkbox
              isChecked={answerMode === 'yesno'}
              onChange={(e) => setAnswerMode(e.target.checked ? 'yesno' : 'checkbox')}
              colorScheme="brand"
            >
              This is a decision (Yes / No)
            </Checkbox>
            <FormHelperText>
              Answer it with a Yes/No button pair. Other tasks can be triggered by the answer.
            </FormHelperText>
          </FormControl>

          <FormControl>
            <FormLabel>Depends on a decision</FormLabel>
            <TaskTriggerBuilder value={trigger} tasks={candidates} onChange={setTrigger} />
          </FormControl>

          {isOneShot && !hasTrigger && (
            <>
              <FormControl>
                <FormLabel>Due date</FormLabel>
                <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
              </FormControl>
              <FormControl>
                <Checkbox
                  isChecked={graceful}
                  onChange={(e) => setGraceful(e.target.checked)}
                  colorScheme="brand"
                >
                  Disappear gracefully when overdue
                </Checkbox>
                <FormHelperText>
                  If checked, a missed task quietly hides instead of nagging as overdue.
                </FormHelperText>
              </FormControl>
            </>
          )}

          <FormControl>
            <FormLabel>Tags</FormLabel>
            <TagInput tags={tags} onChange={setTags} />
          </FormControl>

          <FormControl>
            <FormLabel>Notes</FormLabel>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes"
              rows={3}
            />
          </FormControl>

          <Button type="submit" isLoading={submitting} loadingText="Saving..." width="full">
            {isEdit ? 'Save changes' : 'Add task'}
          </Button>
        </VStack>
      </form>
    </Box>
  );
}
