/**
 * TaskTriggerBuilder — configure a task's dependency on another task's decision.
 *
 * A triggered task stays dormant until its source *decision* task is answered a
 * matching way (Yes / No / either), then activates with a deadline relative to
 * that decision. Clearing the source select removes the trigger (a plain,
 * always-listed task).
 *
 * The source is chosen from a searchable autocomplete (chakra-react-select, as
 * elsewhere in the app), limited to decision tasks — the only tasks that can be
 * answered Yes/No.
 *
 * `value` is the trigger object (or null); `onChange(next|null)` reports edits.
 * `tasks` are the candidate source tasks (self already excluded by the caller);
 * non-decision tasks are filtered out here.
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
import { Select as AutoComplete } from 'chakra-react-select';

const DEFAULT_TRIGGER = { source_task_id: '', on: 'yes', deadline: 'same_day' };

export default function TaskTriggerBuilder({ value, tasks = [], onChange }) {
  const trigger = value || DEFAULT_TRIGGER;
  const decisionTasks = tasks.filter((t) => t.answer_mode === 'yesno');
  const options = decisionTasks.map((t) => ({ value: t.task_id, label: t.name }));
  const selected = options.find((o) => o.value === trigger.source_task_id) || null;

  const patch = (changes) => {
    const next = { ...trigger, ...changes };
    if (next.deadline !== 'offset') delete next.offset_days;
    else if (next.offset_days == null) next.offset_days = 1;
    onChange(next);
  };

  const handleSource = (opt) => {
    if (!opt) {
      onChange(null); // cleared -> no trigger
      return;
    }
    patch({ source_task_id: opt.value });
  };

  return (
    <Box borderWidth="1px" borderColor="gray.200" borderRadius="md" p={3}>
      <FormControl>
        <FormLabel fontSize="sm">Trigger after another task&apos;s decision</FormLabel>
        <AutoComplete
          isClearable
          options={options}
          value={selected}
          onChange={handleSource}
          placeholder={decisionTasks.length ? 'Search decisions…' : 'No decision tasks yet'}
          isDisabled={decisionTasks.length === 0}
          size="sm"
        />
        <FormHelperText>
          {decisionTasks.length
            ? 'This task stays hidden until the chosen decision is answered.'
            : 'Create a Yes/No decision task first, then it can be chosen here.'}
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
    </Box>
  );
}
