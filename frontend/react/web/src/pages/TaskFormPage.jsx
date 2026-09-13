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
  validateTaskName,
  validateRecurrence,
} from '@pantry-app/shared';
import PageHeader from '../components/PageHeader';
import ErrorMessage from '../components/ErrorMessage';
import RecurrenceField from '../components/RecurrenceField';
import TagInput from '../components/TagInput';

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

  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(isEdit);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const isOneShot = recurrence.recurrence_type === 'none';

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
    };
    if (recurrence.recurrence_type === 'interval') {
      payload.recurrence_interval = recurrence.recurrence_interval;
      payload.anchor_date = recurrence.anchor_date || null;
    }
    // A due date only applies to one-shot tasks; clear it otherwise.
    payload.due_date = isOneShot ? dueDate || null : null;

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

          {isOneShot && (
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
