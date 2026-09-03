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
  Select,
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
import { SearchIcon, PlusIcon } from '../components/icons';

// Preset expiry spans (days from today). 'custom' reveals a date picker.
const EXPIRY_PRESETS = [
  { value: '3', label: 'Within 3 days' },
  { value: '7', label: 'Within 1 week' },
  { value: '14', label: 'Within 2 weeks' },
  { value: '30', label: 'Within 1 month' },
  { value: 'custom', label: 'By a date…' },
];

/** Local YYYY-MM-DD (the backend accepts date-only ISO and rejects a trailing Z). */
function toLocalYMD(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export default function SearchPage() {
  const { locationName } = useInventoryContext();

  const [name, setName] = useState('');
  const [locationId, setLocationId] = useState('');
  const [selectedTags, setSelectedTags] = useState([]); // option objects
  const [expiryPreset, setExpiryPreset] = useState(''); // '' | '3' | ... | 'custom'
  const [expiryDate, setExpiryDate] = useState(''); // YYYY-MM-DD when custom

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

  // Resolve the expiry filter to a date-only upper bound, or null.
  const expiryEnd = useCallback(() => {
    if (expiryPreset === 'custom') return expiryDate || null;
    if (expiryPreset) {
      const d = new Date();
      d.setDate(d.getDate() + Number(expiryPreset));
      return toLocalYMD(d);
    }
    return null;
  }, [expiryPreset, expiryDate]);

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
            <Select
              value={expiryPreset}
              onChange={(e) => setExpiryPreset(e.target.value)}
              placeholder="Any expiry"
              bg="white"
              w="170px"
            >
              {EXPIRY_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </Select>
          </WrapItem>
          {expiryPreset === 'custom' && (
            <WrapItem>
              <Input
                type="date"
                value={expiryDate}
                onChange={(e) => setExpiryDate(e.target.value)}
                bg="white"
                w="170px"
              />
            </WrapItem>
          )}
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
