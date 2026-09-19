/**
 * TaskTriggerBuilder — configure a task's dependency on another task's decision.
 *
 * A triggered task stays dormant until its source task is answered a matching
 * way (Yes / No / either), then activates with a deadline relative to that
 * decision. Picking "— None —" clears the trigger (a plain, always-listed task).
 *
 * `value` is the trigger object (or null); `onChange(next|null)` reports edits.
 * `tasks` are the candidate source tasks (self already excluded by the caller).
 */

import {
  Box,
  FormControl,
  FormHelperText,
  FormLabel,
  HStack,
  Input,
  Select,
} from '@chakra-ui/react';

const DEFAULT_TRIGGER = { source_task_id: '', on: 'yes', deadline: 'same_day' };

export default function TaskTriggerBuilder({ value, tasks = [], onChange }) {
  const trigger = value || DEFAULT_TRIGGER;
  const decisionTasks = tasks.filter((t) => t.answer_mode === 'yesno');

  const patch = (changes) => {
    const next = { ...trigger, ...changes };
    // A yes/no branch only makes sense off a decision source.
    if ((next.on === 'yes' || next.on === 'no') && next.source_task_id) {
      const src = tasks.find((t) => t.task_id === next.source_task_id);
      if (src && src.answer_mode !== 'yesno') next.on = 'any';
    }
    if (next.deadline !== 'offset') delete next.offset_days;
    else if (next.offset_days == null) next.offset_days = 1;
    onChange(next);
  };

  const handleSource = (e) => {
    const source_task_id = e.target.value;
    if (!source_task_id) {
      onChange(null); // "— None —" clears the trigger
      return;
    }
    patch({ source_task_id });
  };

  return (
    <Box borderWidth="1px" borderColor="gray.200" borderRadius="md" p={3}>
      <FormControl>
        <FormLabel fontSize="sm">Trigger after another task&apos;s decision</FormLabel>
        <Select value={trigger.source_task_id} onChange={handleSource} placeholder="— None —">
          {tasks.map((t) => (
            <option key={t.task_id} value={t.task_id}>
              {t.name}
              {t.answer_mode === 'yesno' ? ' (decision)' : ''}
            </option>
          ))}
        </Select>
        <FormHelperText>
          This task stays hidden until the chosen task is answered.
        </FormHelperText>
      </FormControl>

      {trigger.source_task_id && (
        <HStack mt={3} align="flex-start" spacing={3}>
          <FormControl>
            <FormLabel fontSize="sm">When answered</FormLabel>
            <Select value={trigger.on} onChange={(e) => patch({ on: e.target.value })}>
              <option value="yes">Yes</option>
              <option value="no">No</option>
              <option value="any">Either</option>
            </Select>
          </FormControl>

          <FormControl>
            <FormLabel fontSize="sm">Due</FormLabel>
            <Select value={trigger.deadline} onChange={(e) => patch({ deadline: e.target.value })}>
              <option value="same_day">Same day</option>
              <option value="same_week">Same week</option>
              <option value="offset">N days after</option>
            </Select>
          </FormControl>

          {trigger.deadline === 'offset' && (
            <FormControl>
              <FormLabel fontSize="sm">Days</FormLabel>
              <Input
                type="number"
                min={0}
                value={trigger.offset_days ?? 1}
                onChange={(e) => patch({ offset_days: Number(e.target.value) })}
              />
            </FormControl>
          )}
        </HStack>
      )}

      {(trigger.on === 'yes' || trigger.on === 'no') && decisionTasks.length === 0 && (
        <FormHelperText color="orange.500">
          A Yes/No trigger needs a decision task as its source.
        </FormHelperText>
      )}
    </Box>
  );
}
