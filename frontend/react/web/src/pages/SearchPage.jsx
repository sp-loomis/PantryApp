/**
 * SearchPage — the app home.
 *
 * Fuzzy-name search over all items with location / tag / expiry filters.
 * An empty query browses everything. Results come from POST /search.
 * Tags filter is multi-select (AND semantics); expiry can be a preset span
 * ("within 2 weeks") or a specific date.
 */

import { useEffect, useState, useCallback, useMemo } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Button,
  Center,
  Flex,
  FormControl,
  FormLabel,
  HStack,
  Input,
  InputGroup,
  InputLeftElement,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Spinner,
  Text,
  useDisclosure,
  useToast,
  VStack,
  Wrap,
  WrapItem,
} from '@chakra-ui/react';
import { Select as MultiSelect } from 'chakra-react-select';
import {
  searchItems,
  listTags,
  updateItemsBulk,
  deleteItemsBulk,
  addItemsTagsBulk,
} from '@pantry-app/shared';
import { useInventoryContext } from '../contexts/InventoryContext';
import LocationSelect from '../components/LocationSelect';
import CategorySelect from '../components/CategorySelect';
import TagInput from '../components/TagInput';
import ConfirmDialog from '../components/ConfirmDialog';
import ItemCard from '../components/ItemCard';
import CategorySummaryCards from '../components/CategorySummaryCards';
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
  const [categoryTotals, setCategoryTotals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Batch selection. `selectMode` reveals per-item checkboxes and the action
  // bar; `selectedIds` is the chosen subset. "Select all" picks every current
  // result, so acting on the whole query is just select-all then an action.
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [locationChoice, setLocationChoice] = useState('');
  const [categoryChoice, setCategoryChoice] = useState('');
  const [tagChoice, setTagChoice] = useState([]);
  const toast = useToast();
  const locationModal = useDisclosure();
  const categoryModal = useDisclosure();
  const tagModal = useDisclosure();
  const confirmDelete = useDisclosure();

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
      const { items: found, categoryTotals: totals } = await searchItems(criteria);
      setItems(found);
      setCategoryTotals(totals);
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

  // Only ids still present in the current results count as selected, so a
  // refreshed/empty result set can't leave stale ids behind.
  const selectedPresent = useMemo(
    () => items.filter((it) => selectedIds.has(it.item_id)),
    [items, selectedIds]
  );
  const selectedCount = selectedPresent.length;
  const allSelected = items.length > 0 && selectedCount === items.length;

  const toggleSelect = useCallback((item) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(item.item_id)) next.delete(item.item_id);
      else next.add(item.item_id);
      return next;
    });
  }, []);

  const selectAll = () => setSelectedIds(new Set(items.map((it) => it.item_id)));
  const deselectAll = () => setSelectedIds(new Set());

  const exitSelectMode = () => {
    setSelectMode(false);
    deselectAll();
  };

  // Summarize a bulk result ("8 updated, 2 skipped") and refresh the view.
  const afterBulk = useCallback(
    async (verb, result) => {
      const done = result.updated ?? result.deleted ?? 0;
      const skipped = result.skipped?.length ?? 0;
      toast({
        title: `${done} ${done === 1 ? 'item' : 'items'} ${verb}`,
        description: skipped ? `${skipped} skipped (incompatible or missing).` : undefined,
        status: skipped ? 'warning' : 'success',
        duration: 4000,
        isClosable: true,
      });
      setSelectMode(false);
      setSelectedIds(new Set());
      await runSearch();
    },
    [toast, runSearch]
  );

  const ids = () => selectedPresent.map((it) => it.item_id);

  const handleChangeLocation = async () => {
    try {
      setBulkBusy(true);
      const result = await updateItemsBulk(ids(), { location_id: locationChoice });
      locationModal.onClose();
      await afterBulk('moved', result);
    } catch (err) {
      setError(err);
    } finally {
      setBulkBusy(false);
    }
  };

  const handleChangeCategory = async () => {
    try {
      setBulkBusy(true);
      // Empty choice clears the category (backend REMOVEs the attribute).
      const result = await updateItemsBulk(ids(), { category_id: categoryChoice || '' });
      categoryModal.onClose();
      await afterBulk('updated', result);
    } catch (err) {
      setError(err);
    } finally {
      setBulkBusy(false);
    }
  };

  const handleAddTags = async () => {
    try {
      setBulkBusy(true);
      const result = await addItemsTagsBulk(ids(), tagChoice);
      tagModal.onClose();
      await afterBulk('tagged', result);
    } catch (err) {
      setError(err);
    } finally {
      setBulkBusy(false);
    }
  };

  const handleDelete = async () => {
    try {
      setBulkBusy(true);
      const result = await deleteItemsBulk(ids());
      confirmDelete.onClose();
      await afterBulk('deleted', result);
    } catch (err) {
      setError(err);
    } finally {
      setBulkBusy(false);
    }
  };

  const openLocationModal = () => {
    setLocationChoice('');
    locationModal.onOpen();
  };
  const openCategoryModal = () => {
    setCategoryChoice('');
    categoryModal.onOpen();
  };
  const openTagModal = () => {
    setTagChoice([]);
    tagModal.onOpen();
  };

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
          <CategorySummaryCards totals={categoryTotals} />
          <HStack justify="space-between" mb={3}>
            <Text color="gray.500" fontSize="sm">
              {selectMode
                ? `${selectedCount} selected`
                : `${items.length} ${items.length === 1 ? 'item' : 'items'}`}
            </Text>
            {selectMode ? (
              <Button size="sm" variant="ghost" onClick={exitSelectMode}>
                Done
              </Button>
            ) : (
              <Button size="sm" variant="outline" onClick={() => setSelectMode(true)}>
                Select
              </Button>
            )}
          </HStack>

          {selectMode && (
            <Wrap spacing={2} align="center" mb={3}>
              <WrapItem>
                <Button
                  size="sm"
                  variant="link"
                  onClick={allSelected ? deselectAll : selectAll}
                >
                  {allSelected ? 'Deselect all' : 'Select all'}
                </Button>
              </WrapItem>
              <WrapItem>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={openLocationModal}
                  isDisabled={selectedCount === 0 || bulkBusy}
                >
                  Change location
                </Button>
              </WrapItem>
              <WrapItem>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={openCategoryModal}
                  isDisabled={selectedCount === 0 || bulkBusy}
                >
                  Change category
                </Button>
              </WrapItem>
              <WrapItem>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={openTagModal}
                  isDisabled={selectedCount === 0 || bulkBusy}
                >
                  Add tags
                </Button>
              </WrapItem>
              <WrapItem>
                <Button
                  size="sm"
                  variant="outline"
                  colorScheme="red"
                  onClick={confirmDelete.onOpen}
                  isDisabled={selectedCount === 0 || bulkBusy}
                >
                  Delete
                </Button>
              </WrapItem>
            </Wrap>
          )}

          <VStack spacing={3} align="stretch">
            {items.map((item) => (
              <ItemCard
                key={item.item_id}
                item={item}
                locationName={locationName(item.location_id)}
                selectable={selectMode}
                selected={selectedIds.has(item.item_id)}
                onToggleSelect={toggleSelect}
              />
            ))}
          </VStack>
        </>
      )}

      <Modal isOpen={locationModal.isOpen} onClose={locationModal.onClose} isCentered>
        <ModalOverlay />
        <ModalContent mx={4}>
          <ModalHeader>Change location</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl>
              <FormLabel>
                Move {selectedCount} {selectedCount === 1 ? 'item' : 'items'} to
              </FormLabel>
              <LocationSelect
                value={locationChoice}
                onChange={(e) => setLocationChoice(e.target.value)}
                placeholder="Select a location"
              />
            </FormControl>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={locationModal.onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="brand"
              onClick={handleChangeLocation}
              isDisabled={!locationChoice}
              isLoading={bulkBusy}
            >
              Apply
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal isOpen={categoryModal.isOpen} onClose={categoryModal.onClose} isCentered>
        <ModalOverlay />
        <ModalContent mx={4}>
          <ModalHeader>Change category</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl>
              <FormLabel>
                Set category on {selectedCount} {selectedCount === 1 ? 'item' : 'items'}
              </FormLabel>
              {/* includeAllTypes: a mixed selection may include items a category
                  can't accept; offer every category and let the backend apply
                  where valid, reporting the rest as skipped. */}
              <CategorySelect
                value={categoryChoice}
                onChange={(e) => setCategoryChoice(e.target.value)}
                includeAllTypes
                placeholder="No category (clear)"
              />
            </FormControl>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={categoryModal.onClose}>
              Cancel
            </Button>
            <Button colorScheme="brand" onClick={handleChangeCategory} isLoading={bulkBusy}>
              Apply
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal isOpen={tagModal.isOpen} onClose={tagModal.onClose} isCentered>
        <ModalOverlay />
        <ModalContent mx={4}>
          <ModalHeader>Add tags</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl>
              <FormLabel>
                Add tags to {selectedCount} {selectedCount === 1 ? 'item' : 'items'}
              </FormLabel>
              {/* Additive: tags merge into each item's existing set. */}
              <TagInput tags={tagChoice} onChange={setTagChoice} />
            </FormControl>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={tagModal.onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="brand"
              onClick={handleAddTags}
              isDisabled={tagChoice.length === 0}
              isLoading={bulkBusy}
            >
              Apply
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <ConfirmDialog
        isOpen={confirmDelete.isOpen}
        onClose={confirmDelete.onClose}
        onConfirm={handleDelete}
        isLoading={bulkBusy}
        title="Delete items"
        body={`Delete ${selectedCount} ${
          selectedCount === 1 ? 'item' : 'items'
        }? This can't be undone.`}
        confirmLabel="Delete"
      />
    </Box>
  );
}
