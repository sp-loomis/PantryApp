/**
 * CategoryFormPage — create or edit an item category.
 *
 * A category has a measure type (count / weight / volume). Weight and volume
 * categories also carry a preferred unit (the conversion/reporting target);
 * count categories have none — they aggregate as a plain item count.
 */

import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Center,
  FormControl,
  FormHelperText,
  FormLabel,
  HStack,
  Input,
  Select,
  Spinner,
  Textarea,
  useDisclosure,
  VStack,
  Text,
} from '@chakra-ui/react';
import {
  getCategory,
  createCategory,
  updateCategory,
  deleteCategory,
  UNITS,
  DEFAULT_UNIT,
} from '@pantry-app/shared';
import PageHeader from '../components/PageHeader';
import ErrorMessage from '../components/ErrorMessage';
import ConfirmDialog from '../components/ConfirmDialog';

const MEASURE_TYPES = ['count', 'weight', 'volume'];

export default function CategoryFormPage() {
  const { categoryId } = useParams();
  const isEdit = Boolean(categoryId);
  const navigate = useNavigate();
  const confirm = useDisclosure();

  const [name, setName] = useState('');
  const [measureType, setMeasureType] = useState('weight');
  const [preferredUnit, setPreferredUnit] = useState(DEFAULT_UNIT.weight);
  const [description, setDescription] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(isEdit);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadExisting = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const cat = await getCategory(categoryId);
      setName(cat.name);
      setMeasureType(cat.measure_type);
      setPreferredUnit(cat.preferred_unit || '');
      setDescription(cat.description || '');
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [categoryId]);

  useEffect(() => {
    if (isEdit) loadExisting();
  }, [isEdit, loadExisting]);

  // When the measure type changes, reset the unit to a sensible default (or clear
  // it for count, which has no unit).
  const handleMeasureTypeChange = (e) => {
    const next = e.target.value;
    setMeasureType(next);
    setPreferredUnit(next === 'count' ? '' : DEFAULT_UNIT[next] || (UNITS[next]?.[0] ?? ''));
  };

  const validate = () => {
    const errors = {};
    if (!name.trim()) errors.name = 'Name is required';
    if (measureType !== 'count' && !preferredUnit) {
      errors.preferredUnit = 'Choose a preferred unit';
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    const payload = {
      name: name.trim(),
      measure_type: measureType,
      preferred_unit: measureType === 'count' ? null : preferredUnit,
      description,
    };

    try {
      setSubmitting(true);
      setError(null);
      if (isEdit) {
        await updateCategory(categoryId, payload);
      } else {
        await createCategory(payload);
      }
      navigate('/categories');
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    try {
      setDeleting(true);
      await deleteCategory(categoryId);
      navigate('/categories');
    } catch (err) {
      setError(err);
      setDeleting(false);
      confirm.onClose();
    }
  };

  if (loading) {
    return (
      <Center py={12}>
        <Spinner color="brand.500" thickness="3px" />
      </Center>
    );
  }

  const unitOptions = UNITS[measureType] || [];

  return (
    <Box>
      <PageHeader title={isEdit ? 'Edit category' : 'New category'} back />
      <ErrorMessage error={error} />

      <form onSubmit={handleSubmit}>
        <VStack spacing={4} align="stretch" maxW="480px">
          <FormControl isInvalid={!!fieldErrors.name} isRequired>
            <FormLabel>Name</FormLabel>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Beef"
              autoFocus
            />
            {fieldErrors.name && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {fieldErrors.name}
              </Text>
            )}
          </FormControl>

          <FormControl isRequired>
            <FormLabel>Measure type</FormLabel>
            <Select value={measureType} onChange={handleMeasureTypeChange}>
              {MEASURE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
            <FormHelperText>
              Count totals the number of items; weight/volume sum the item measures.
            </FormHelperText>
          </FormControl>

          {measureType !== 'count' && (
            <FormControl isInvalid={!!fieldErrors.preferredUnit} isRequired>
              <FormLabel>Preferred unit</FormLabel>
              <Select value={preferredUnit} onChange={(e) => setPreferredUnit(e.target.value)}>
                {unitOptions.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </Select>
              <FormHelperText>Totals are converted to this unit for reporting.</FormHelperText>
              {fieldErrors.preferredUnit && (
                <Text color="red.500" fontSize="sm" mt={1}>
                  {fieldErrors.preferredUnit}
                </Text>
              )}
            </FormControl>
          )}

          <FormControl>
            <FormLabel>Description</FormLabel>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional notes about this category"
              rows={3}
            />
          </FormControl>

          <HStack>
            <Button type="submit" isLoading={submitting} loadingText="Saving..." flex="1">
              {isEdit ? 'Save changes' : 'Create category'}
            </Button>
            {isEdit && (
              <Button colorScheme="red" variant="outline" onClick={confirm.onOpen}>
                Delete
              </Button>
            )}
          </HStack>
        </VStack>
      </form>

      <ConfirmDialog
        isOpen={confirm.isOpen}
        onClose={confirm.onClose}
        onConfirm={handleDelete}
        isLoading={deleting}
        title="Delete category"
        body="This removes the category from any items that use it. This cannot be undone."
      />
    </Box>
  );
}
