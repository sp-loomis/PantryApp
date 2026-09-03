/**
 * TagDetailPage — all items carrying a given tag.
 */

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Center, Spinner, Text, VStack } from '@chakra-ui/react';
import { listItems } from '@pantry-app/shared';
import { useInventoryContext } from '../contexts/InventoryContext';
import PageHeader from '../components/PageHeader';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import ItemCard from '../components/ItemCard';

export default function TagDetailPage() {
  const { tag } = useParams();
  const { locationName } = useInventoryContext();

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setItems(await listItems({ tag }));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [tag]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Box>
      <PageHeader title={`#${tag}`} subtitle="Tagged items" back="/tags" />
      <ErrorMessage error={error} />

      {loading ? (
        <Center py={12}>
          <Spinner color="brand.500" thickness="3px" />
        </Center>
      ) : items.length === 0 ? (
        <EmptyState title="No items with this tag" />
      ) : (
        <>
          <Text color="gray.500" fontSize="sm" mb={3}>
            {items.length} {items.length === 1 ? 'item' : 'items'}
          </Text>
          <VStack spacing={3} align="stretch">
            {items.map((item) => (
              <ItemCard
                key={item.item_id}
                item={item}
                locationName={locationName(item.location_id)}
              />
            ))}
          </VStack>
        </>
      )}
    </Box>
  );
}
