/**
 * CategorySelect
 *
 * A <Select> of the user's categories. Loads them on mount (categories are not in
 * InventoryContext). When `measureType` is given, only categories an item with
 * that measure can join are offered: `count` categories accept any item; a
 * `weight`/`volume` category needs a matching dimension, so it appears only when
 * the item's measure type matches.
 */

import { useEffect, useState } from 'react';
import { Select } from '@chakra-ui/react';
import { listCategories } from '@pantry-app/shared';

function compatible(category, measureType) {
  if (category.measure_type === 'count') return true;
  return category.measure_type === measureType;
}

export default function CategorySelect({
  value,
  onChange,
  measureType,
  placeholder = 'No category',
  ...props
}) {
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    let active = true;
    listCategories()
      .then((cats) => active && setCategories(cats))
      .catch(() => active && setCategories([]));
    return () => {
      active = false;
    };
  }, []);

  const options = categories.filter((c) => compatible(c, measureType));
  // Keep a currently-selected-but-now-incompatible category visible so editing an
  // item doesn't silently drop its assignment.
  const selectedMissing = value && !options.some((c) => c.category_id === value);
  const selected = selectedMissing && categories.find((c) => c.category_id === value);

  return (
    <Select value={value || ''} onChange={onChange} placeholder={placeholder} {...props}>
      {options.map((c) => (
        <option key={c.category_id} value={c.category_id}>
          {c.name} ({c.measure_type}
          {c.preferred_unit ? ` · ${c.preferred_unit}` : ''})
        </option>
      ))}
      {selected && (
        <option value={selected.category_id}>
          {selected.name} ({selected.measure_type})
        </option>
      )}
    </Select>
  );
}
