/**
 * RecurrenceField
 *
 * Controlled recurrence editor for the task form. Emits a value object:
 *   { recurrence_type, recurrence_interval, anchor_date }
 * Reveals the interval stepper + anchor date only for the "interval" type.
 */

import {
  FormControl,
  FormLabel,
  FormHelperText,
  HStack,
  Input,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Select,
  VStack,
} from '@chakra-ui/react';

const OPTIONS = [
  { value: 'none', label: 'One-time' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'interval', label: 'Every N days' },
];

export default function RecurrenceField({ value, onChange }) {
  const { recurrence_type = 'none', recurrence_interval, anchor_date } = value;

  const set = (patch) => onChange({ ...value, ...patch });

  return (
    <FormControl>
      <FormLabel>Repeat</FormLabel>
      <VStack spacing={3} align="stretch">
        <Select
          value={recurrence_type}
          onChange={(e) => set({ recurrence_type: e.target.value })}
        >
          {OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>

        {recurrence_type === 'interval' && (
          <HStack align="flex-end" spacing={3}>
            <FormControl>
              <FormLabel fontSize="sm" color="gray.500">
                Every (days)
              </FormLabel>
              <NumberInput
                min={1}
                max={365}
                value={recurrence_interval ?? 2}
                onChange={(_, num) => set({ recurrence_interval: Number.isNaN(num) ? 1 : num })}
              >
                <NumberInputField inputMode="numeric" />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
            </FormControl>
            <FormControl>
              <FormLabel fontSize="sm" color="gray.500">
                Starting
              </FormLabel>
              <Input
                type="date"
                value={anchor_date || ''}
                onChange={(e) => set({ anchor_date: e.target.value })}
              />
            </FormControl>
          </HStack>
        )}
      </VStack>
      {recurrence_type !== 'none' && (
        <FormHelperText>
          Recurring chores gracefully disappear when a window passes — a missed day never piles up.
        </FormHelperText>
      )}
    </FormControl>
  );
}
