/**
 * SearchPage — the app home.
 *
 * Fuzzy-name search over all items with location / tag / expiry filters.
 * An empty query browses everything. Results come from POST /search.
 * Tags filter is multi-select (AND semantics); expiry can be a preset span
 * ("within 2 weeks") or a specific date.
 */

import { useEffect, useState, useCallback } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Button,
  Center,
  Flex,
  HStack,
  Input,
  InputGroup,
  InputLeftElement,
  Spinner,
  Text,
  VStack,
  Wrap,
  WrapItem,
} from '@chakra-ui/react';
import { Select as MultiSelect } from 'chakra-react-select';
import { searchItems, listTags } from '@pantry-app/shared';
import { useInventoryContext } from '../contexts/InventoryContext';
import LocationSelect from '../components/LocationSelect';
import ItemCard from '../components/ItemCard';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import ExpiryFilter from '../components/ExpiryFilter';
import { presetToDate } from '../utils/expiry';
import { SearchIcon, PlusIcon } from '../components/icons';

export default function SearchPage() {
  const { locationName } = useInventoryContext();

  const [name, setName] = useState('');
  const [locationId, setLocationId] = useState('');
  const [selectedTags, setSelectedTags] = useState([]); // option objects
  const [expiry, setExpiry] = useState({}); // { withinDays?, dateEnd? }

  const [tagOptions, setTagOptions] = useState([]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load the tag list once for the tag filter.
  useEffect(() => {
    listTags()
      .then((all) => setTagOptions(all.map((t) => ({ value: t, label: t }))))
      .catch(() => setTagOptions([]));
  }, []);

  // Resolve the expiry filter to a date-only upper bound, or null. A relative
  // span (withinDays) resolves against today; a custom date passes through.
  const expiryEnd = useCallback(() => {
    if (expiry.withinDays) return presetToDate(expiry.withinDays);
    return expiry.dateEnd || null;
  }, [expiry]);

  const runSearch = useCallback(async () => {
    const criteria = {};
    if (name.trim()) criteria.name = name.trim();
    if (locationId) criteria.location_id = locationId;
    if (selectedTags.length) criteria.tags = selectedTags.map((o) => o.value);
    const end = expiryEnd();
    if (end) criteria.use_by_date_end = end;

    try {
      setLoading(true);
      setError(null);
      setItems(await searchItems(criteria));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [name, locationId, selectedTags, expiryEnd]);

  // Debounce so typing does not fire a request per keystroke.
  useEffect(() => {
    const handle = setTimeout(runSearch, 250);
    return () => clearTimeout(handle);
  }, [runSearch]);

  const hasFilters = Boolean(
    name || locationId || selectedTags.length || expiryEnd()
  );

  return (
    <Box>
      <Flex align="center" justify="space-between" mb={4} gap={3}>
        <Text fontSize="2xl" fontWeight="bold">
          Pantry
        </Text>
        <Button as={RouterLink} to="/items/new" leftIcon={<PlusIcon boxSize={4} />}>
          Add item
        </Button>
      </Flex>

      <VStack spacing={3} align="stretch" mb={5}>
        <InputGroup>
          <InputLeftElement pointerEvents="none">
            <SearchIcon boxSize={5} color="gray.400" />
          </InputLeftElement>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Search items"
            bg="white"
          />
        </InputGroup>

        <Wrap spacing={3} align="center">
          <WrapItem>
            <LocationSelect
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
              placeholder="All locations"
              bg="white"
              w="200px"
            />
          </WrapItem>
          <WrapItem>
            <Box minW="220px">
              <MultiSelect
                isMulti
                options={tagOptions}
                value={selectedTags}
                onChange={(selected) => setSelectedTags(selected || [])}
                placeholder="All tags"
                size="md"
              />
            </Box>
          </WrapItem>
          <WrapItem>
            <ExpiryFilter
              withinDays={expiry.withinDays}
              dateEnd={expiry.dateEnd}
              onChange={setExpiry}
              bg="white"
            />
          </WrapItem>
        </Wrap>
      </VStack>

      <ErrorMessage error={error} />

      {loading ? (
        <Center py={12}>
          <Spinner color="brand.500" thickness="3px" />
        </Center>
      ) : items.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No matching items' : 'Your pantry is empty'}
          description={
            hasFilters
              ? 'Try adjusting your search or filters.'
              : 'Add your first item to get started.'
          }
          action={
            !hasFilters && (
              <Button as={RouterLink} to="/items/new" mt={2}>
                Add item
              </Button>
            )
          }
        />
      ) : (
        <>
          <HStack justify="space-between" mb={3}>
            <Text color="gray.500" fontSize="sm">
              {items.length} {items.length === 1 ? 'item' : 'items'}
            </Text>
          </HStack>
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
