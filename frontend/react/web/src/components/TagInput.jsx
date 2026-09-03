/**
 * TagInput
 *
 * Creatable, autocompleting multi-tag editor for the item form. Suggests
 * existing tags (GET /tags) and lets you create new ones. Tags are lowercased
 * and de-duplicated to match backend storage.
 *
 * External API is unchanged: `tags` (string[]) + `onChange(string[])`.
 */

import { useEffect, useState } from 'react';
import { CreatableSelect } from 'chakra-react-select';
import { listTags } from '@pantry-app/shared';

export default function TagInput({ tags, onChange }) {
  const [options, setOptions] = useState([]);

  useEffect(() => {
    listTags()
      .then((all) => setOptions(all.map((t) => ({ value: t, label: t }))))
      .catch(() => setOptions([]));
  }, []);

  const value = tags.map((t) => ({ value: t, label: t }));

  const handleChange = (selected) => {
    const next = (selected || [])
      .map((opt) => opt.value.trim().toLowerCase())
      .filter(Boolean);
    onChange([...new Set(next)]);
  };

  return (
    <CreatableSelect
      isMulti
      options={options}
      value={value}
      onChange={handleChange}
      placeholder="Add tags"
      formatCreateLabel={(input) => `Add "${input.trim().toLowerCase()}"`}
      // Keep the created tag lowercased in the menu option.
      createOptionPosition="first"
      size="md"
    />
  );
}
