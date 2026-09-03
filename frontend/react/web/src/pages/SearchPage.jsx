/**
 * SearchPage — the app home.
 *
 * Fuzzy-name search over all items with location / tag / expiring filters.
 * An empty query browses everything. Results come from POST /search.
 */

import { useEffect, useState, useCallback } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Button,
  Center,
  Checkbox,
  Flex,
  HStack,
  Input,
  InputGroup,
  InputLeftElement,
  Select,
  Spinner,
  Text,
  VStack,
  Wrap,
  WrapItem,
} from '@chakra-ui/react';
import { searchItems, listTags } from '@pantry-app/shared';
import { useInventoryContext } from '../contexts/InventoryContext';
import LocationSelect from '../components/LocationSelect';
import ItemCard from '../components/ItemCard';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import { SearchIcon, PlusIcon } from '../components/icons';

const EXPIRING_WINDOW_DAYS = 7;

export default function SearchPage() {
  const { locationName } = useInventoryContext();

  const [name, setName] = useState('');
  const [locationId, setLocationId] = useState('');
  const [tag, setTag] = useState('');
  const [expiring, setExpiring] = useState(false);

  const [allTags, setAllTags] = useState([]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load the tag list once for the tag filter.
  useEffect(() => {
    listTags()
      .then(setAllTags)
      .catch(() => setAllTags([]));
  }, []);

  const runSearch = useCallback(async () => {
    const criteria = {};
    if (name.trim()) criteria.name = name.trim();
    if (locationId) criteria.location_id = locationId;
    if (tag) criteria.tags = [tag];
    if (expiring) {
      criteria.use_by_date_end = new Date(
        Date.now() + EXPIRING_WINDOW_DAYS * 24 * 60 * 60 * 1000
      ).toISOString();
    }
    try {
      setLoading(true);
      setError(null);
      setItems(await searchItems(criteria));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [name, locationId, tag, expiring]);

  // Debounce so typing does not fire a request per keystroke.
  useEffect(() => {
    const handle = setTimeout(runSearch, 250);
    return () => clearTimeout(handle);
  }, [runSearch]);

  const hasFilters = Boolean(name || locationId || tag || expiring);

  return (
    <Box>
      <Flex align="center" justify="space-between" mb={4} gap={3}>
        <Box>
          <Text fontSize="2xl" fontWeight="bold">
            Pantry
          </Text>
        </Box>
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
            <Select
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              placeholder="All tags"
              bg="white"
              w="180px"
            >
              {allTags.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
          </WrapItem>
          <WrapItem>
            <Checkbox isChecked={expiring} onChange={(e) => setExpiring(e.target.checked)}>
              Expiring soon
            </Checkbox>
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
