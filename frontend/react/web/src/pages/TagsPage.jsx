/**
 * TagsPage — index of all tags across the user's inventory.
 */

import { useEffect, useState, useCallback } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Box, Center, Spinner, Tag, TagLabel, Wrap, WrapItem, Link } from '@chakra-ui/react';
import { listTags } from '@pantry-app/shared';
import PageHeader from '../components/PageHeader';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import { TagIcon } from '../components/icons';

export default function TagsPage() {
  const [tags, setTags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setTags(await listTags());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Box>
      <PageHeader title="Tags" />
      <ErrorMessage error={error} />

      {loading ? (
        <Center py={12}>
          <Spinner color="brand.500" thickness="3px" />
        </Center>
      ) : tags.length === 0 ? (
        <EmptyState
          title="No tags yet"
          description="Tags you add to items will show up here."
        />
      ) : (
        <Wrap spacing={3}>
          {tags.map((tag) => (
            <WrapItem key={tag}>
              <Link as={RouterLink} to={`/tags/${encodeURIComponent(tag)}`}>
                <Tag size="lg" colorScheme="brand" variant="subtle" borderRadius="full">
                  <TagIcon boxSize={3.5} mr={2} />
                  <TagLabel>{tag}</TagLabel>
                </Tag>
              </Link>
            </WrapItem>
          ))}
        </Wrap>
      )}
    </Box>
  );
}
