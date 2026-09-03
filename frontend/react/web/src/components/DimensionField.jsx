/**
 * DimensionField
 *
 * The item form's single OPTIONAL measure control: a Weight/Volume toggle, an
 * amount, and a unit. Controlled via a measure object `{ type, value, unit }`.
 * Selecting the active type again (or "Clear") unsets the measure.
 */

import {
  FormControl,
  FormLabel,
  HStack,
  Button,
  NumberInput,
  NumberInputField,
  Select,
  Text,
} from '@chakra-ui/react';
import { UNITS, DEFAULT_UNIT, EMPTY_MEASURE } from '@pantry-app/shared';

export default function DimensionField({ value, onChange, error }) {
  const { type, value: amount, unit } = value;

  const pickType = (next) => {
    if (next === type) {
      onChange({ ...EMPTY_MEASURE });
      return;
    }
    onChange({ type: next, value: amount ?? '', unit: DEFAULT_UNIT[next] });
  };

  return (
    <FormControl isInvalid={!!error}>
      <FormLabel mb={2}>
        Measure{' '}
        <Text as="span" color="gray.400" fontWeight="normal">
          (optional)
        </Text>
      </FormLabel>

      <HStack mb={type ? 3 : 0}>
        <Button
          flex="1"
          variant={type === 'weight' ? 'solid' : 'outline'}
          onClick={() => pickType('weight')}
        >
          Weight
        </Button>
        <Button
          flex="1"
          variant={type === 'volume' ? 'solid' : 'outline'}
          onClick={() => pickType('volume')}
        >
          Volume
        </Button>
      </HStack>

      {type && (
        <HStack align="stretch">
          <NumberInput
            flex="1"
            min={0}
            value={amount}
            onChange={(str) => onChange({ type, value: str, unit })}
          >
            <NumberInputField placeholder="Amount" inputMode="decimal" />
          </NumberInput>
          <Select
            w="140px"
            value={unit}
            onChange={(e) => onChange({ type, value: amount, unit: e.target.value })}
          >
            {UNITS[type].map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </Select>
        </HStack>
      )}

      {error && (
        <Text color="red.500" fontSize="sm" mt={1}>
          {error}
        </Text>
      )}

      {type && (
        <Button size="xs" variant="link" mt={2} onClick={() => onChange({ ...EMPTY_MEASURE })}>
          Clear measure
        </Button>
      )}
    </FormControl>
  );
}
