/**
 * LocationSelect
 *
 * A <Select> of the user's storage locations, sourced from InventoryContext.
 */

import { Select } from '@chakra-ui/react';
import { useInventoryContext } from '../contexts/InventoryContext';

export default function LocationSelect({ value, onChange, placeholder = 'All locations', ...props }) {
  const { locations } = useInventoryContext();

  return (
    <Select value={value} onChange={onChange} placeholder={placeholder} {...props}>
      {locations.map((loc) => (
        <option key={loc.location_id} value={loc.location_id}>
          {loc.name}
        </option>
      ))}
    </Select>
  );
}
