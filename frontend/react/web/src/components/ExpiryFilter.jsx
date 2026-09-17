/**
 * ExpiryFilter — the shared "expires by" filter control.
 *
 * A preset span ("within 2 weeks") or a specific date ("By a date…"). Used by
 * the Search page and by report item-queries / trigger conditions so all three
 * offer the same expiry options.
 *
 * It reports its value as `{ withinDays, dateEnd }`:
 *   - a preset sets `withinDays` (3/7/14/30) and clears `dateEnd`;
 *   - the custom date sets `dateEnd` (YYYY-MM-DD) and clears `withinDays`;
 *   - "Any expiry" clears both.
 *
 * The caller decides what to do with that: the Search page resolves a relative
 * span to an absolute date at query time; reports store it relative so a
 * recurring run recomputes "within N days" each time.
 */

import { useState } from 'react';
import { HStack, Input, Select } from '@chakra-ui/react';
import { EXPIRY_PRESETS } from '../utils/expiry';

function initialPreset(withinDays, dateEnd) {
  if (dateEnd) return 'custom';
  if (withinDays !== undefined && withinDays !== null && withinDays !== '') {
    return String(withinDays);
  }
  return '';
}

export default function ExpiryFilter({
  withinDays,
  dateEnd,
  onChange,
  width = '170px',
  bg,
}) {
  // Local so the "custom, no date yet" state survives (props would collapse it).
  const [preset, setPreset] = useState(() => initialPreset(withinDays, dateEnd));
  const [date, setDate] = useState(dateEnd || '');

  const emit = (nextPreset, nextDate) => {
    if (nextPreset === 'custom') {
      onChange({ withinDays: undefined, dateEnd: nextDate || undefined });
    } else if (nextPreset) {
      onChange({ withinDays: Number(nextPreset), dateEnd: undefined });
    } else {
      onChange({ withinDays: undefined, dateEnd: undefined });
    }
  };

  const handlePreset = (value) => {
    setPreset(value);
    if (value !== 'custom') setDate('');
    emit(value, value === 'custom' ? date : '');
  };

  const handleDate = (value) => {
    setDate(value);
    emit('custom', value);
  };

  return (
    <HStack spacing={3} align="center">
      <Select
        value={preset}
        onChange={(e) => handlePreset(e.target.value)}
        placeholder="Any expiry"
        bg={bg}
        w={width}
      >
        {EXPIRY_PRESETS.map((p) => (
          <option key={p.value} value={p.value}>
            {p.label}
          </option>
        ))}
      </Select>
      {preset === 'custom' && (
        <Input
          type="date"
          value={date}
          onChange={(e) => handleDate(e.target.value)}
          bg={bg}
          w={width}
        />
      )}
    </HStack>
  );
}
