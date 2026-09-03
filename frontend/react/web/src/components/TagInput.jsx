/**
 * TagInput
 *
 * Lightweight tag editor: type a tag, press Enter or comma (or Add) to append;
 * tags render as removable chips. Tags are lowercased to match backend storage.
 */

import { useState } from 'react';
import {
  Box,
  HStack,
  Input,
  Button,
  Tag,
  TagLabel,
  TagCloseButton,
  Wrap,
  WrapItem,
} from '@chakra-ui/react';

export default function TagInput({ tags, onChange }) {
  const [draft, setDraft] = useState('');

  const addTag = () => {
    const next = draft.trim().toLowerCase();
    if (next && !tags.includes(next)) {
      onChange([...tags, next]);
    }
    setDraft('');
  };

  const removeTag = (tag) => onChange(tags.filter((t) => t !== tag));

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag();
    }
  };

  return (
    <Box>
      <HStack>
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Add a tag"
        />
        <Button onClick={addTag} variant="outline" flexShrink={0}>
          Add
        </Button>
      </HStack>

      {tags.length > 0 && (
        <Wrap mt={2} spacing={2}>
          {tags.map((tag) => (
            <WrapItem key={tag}>
              <Tag colorScheme="brand" variant="subtle" size="md">
                <TagLabel>{tag}</TagLabel>
                <TagCloseButton onClick={() => removeTag(tag)} />
              </Tag>
            </WrapItem>
          ))}
        </Wrap>
      )}
    </Box>
  );
}
