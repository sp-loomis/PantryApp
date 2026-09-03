/**
 * ItemFormPage — create or edit an inventory item.
 *
 * Uses controlled state because several fields are custom controls
 * (DimensionField, LocationSelect, TagInput).
 */

import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Box,
  Button,
  Center,
  FormControl,
  FormHelperText,
  FormLabel,
  Input,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Spinner,
  Textarea,
  useToast,
  VStack,
  Text,
} from '@chakra-ui/react';
import {
  getItem,
  createItem,
  updateItem,
  validateItemName,
  validateMeasure,
  measureToDimensions,
  dimensionsToMeasure,
  EMPTY_MEASURE,
} from '@pantry-app/shared';
import { useInventoryContext } from '../contexts/InventoryContext';
import PageHeader from '../components/PageHeader';
import ErrorMessage from '../components/ErrorMessage';
import DimensionField from '../components/DimensionField';
import LocationSelect from '../components/LocationSelect';
import TagInput from '../components/TagInput';

export default function ItemFormPage() {
  const { itemId } = useParams();
  const isEdit = Boolean(itemId);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { reloadLocations } = useInventoryContext();
  const toast = useToast();

  const [name, setName] = useState('');
  const [locationId, setLocationId] = useState(searchParams.get('location') || '');
  const [measure, setMeasure] = useState({ ...EMPTY_MEASURE });
  const [useByDate, setUseByDate] = useState('');
  const [tags, setTags] = useState([]);
  const [notes, setNotes] = useState('');
  // Number of identical copies to create (create mode only).
  const [copies, setCopies] = useState('1');

  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(isEdit);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const loadExisting = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const item = await getItem(itemId);
      setName(item.name);
      setLocationId(item.location_id);
      setMeasure(dimensionsToMeasure(item.dimensions));
      setUseByDate(item.use_by_date ? item.use_by_date.slice(0, 10) : '');
      setTags(item.tags || []);
      setNotes(item.notes || '');
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [itemId]);

  useEffect(() => {
    if (isEdit) loadExisting();
  }, [isEdit, loadExisting]);

  const validate = () => {
    const errors = {};
    const nameErr = validateItemName(name);
    if (nameErr) errors.name = nameErr;
    if (!locationId) errors.location = 'Location is required';
    const measureErr = validateMeasure(measure);
    if (measureErr) errors.measure = measureErr;
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    const payload = {
      name: name.trim(),
      location_id: locationId,
      dimensions: measureToDimensions(measure),
      use_by_date: useByDate || null,
      tags,
      notes,
    };

    // How many copies to create (create mode only). Clamp defensively; the
    // backend enforces the same [1, 100] bound.
    const numCopies = isEdit
      ? 1
      : Math.max(1, Math.min(100, parseInt(copies, 10) || 1));
    if (!isEdit) payload.copies = numCopies;

    try {
      setSubmitting(true);
      setError(null);
      const saved = isEdit ? await updateItem(itemId, payload) : await createItem(payload);

      if (isEdit) {
        navigate(`/items/${itemId}`);
        return;
      }

      // A new item may introduce a first-use of a location; keep context fresh.
      await reloadLocations();

      // createItem returns a single object for one copy, an array for several.
      const created = Array.isArray(saved) ? saved : [saved];
      if (created.length === 1) {
        navigate(`/items/${created[0].item_id}`);
      } else {
        toast({
          title: `Added ${created.length} copies of ${payload.name}`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        navigate(-1);
      }
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Center py={12}>
        <Spinner color="brand.500" thickness="3px" />
      </Center>
    );
  }

  return (
    <Box>
      <PageHeader title={isEdit ? 'Edit item' : 'New item'} back />
      <ErrorMessage error={error} />

      <form onSubmit={handleSubmit}>
        <VStack spacing={4} align="stretch" maxW="480px">
          <FormControl isInvalid={!!fieldErrors.name} isRequired>
            <FormLabel>Name</FormLabel>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. All-Purpose Flour"
              autoFocus
            />
            {fieldErrors.name && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {fieldErrors.name}
              </Text>
            )}
          </FormControl>

          <FormControl isInvalid={!!fieldErrors.location} isRequired>
            <FormLabel>Location</FormLabel>
            <LocationSelect
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
              placeholder="Select a location"
            />
            {fieldErrors.location && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {fieldErrors.location}
              </Text>
            )}
          </FormControl>

          <DimensionField value={measure} onChange={setMeasure} error={fieldErrors.measure} />

          <FormControl>
            <FormLabel>Use-by date</FormLabel>
            <Input
              type="date"
              value={useByDate}
              onChange={(e) => setUseByDate(e.target.value)}
            />
          </FormControl>

          <FormControl>
            <FormLabel>Tags</FormLabel>
            <TagInput tags={tags} onChange={setTags} />
          </FormControl>

          <FormControl>
            <FormLabel>Notes</FormLabel>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes"
              rows={3}
            />
          </FormControl>

          {!isEdit && (
            <FormControl>
              <FormLabel>Copies</FormLabel>
              <NumberInput
                min={1}
                max={100}
                value={copies}
                onChange={(str) => setCopies(str)}
              >
                <NumberInputField inputMode="numeric" />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <FormHelperText>Add several identical entries at once (up to 100).</FormHelperText>
            </FormControl>
          )}

          <Button type="submit" isLoading={submitting} loadingText="Saving..." width="full">
            {isEdit ? 'Save changes' : 'Add item'}
          </Button>
        </VStack>
      </form>
    </Box>
  );
}
