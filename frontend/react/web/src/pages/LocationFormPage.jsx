/**
 * LocationFormPage — create or edit a storage location.
 */

import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Center,
  FormControl,
  FormLabel,
  Input,
  Spinner,
  Textarea,
  VStack,
  Text,
} from '@chakra-ui/react';
import {
  getLocation,
  createLocation,
  updateLocation,
  validateLocationName,
} from '@pantry-app/shared';
import { useInventoryContext } from '../contexts/InventoryContext';
import PageHeader from '../components/PageHeader';
import ErrorMessage from '../components/ErrorMessage';

export default function LocationFormPage() {
  const { locationId } = useParams();
  const isEdit = Boolean(locationId);
  const navigate = useNavigate();
  const { reloadLocations } = useInventoryContext();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [nameError, setNameError] = useState(null);
  const [loading, setLoading] = useState(isEdit);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const loadExisting = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const loc = await getLocation(locationId);
      setName(loc.name);
      setDescription(loc.description || '');
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [locationId]);

  useEffect(() => {
    if (isEdit) loadExisting();
  }, [isEdit, loadExisting]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const nameErr = validateLocationName(name);
    setNameError(nameErr);
    if (nameErr) return;

    try {
      setSubmitting(true);
      setError(null);
      let saved;
      if (isEdit) {
        saved = await updateLocation(locationId, { name: name.trim(), description });
      } else {
        saved = await createLocation({ name: name.trim(), description });
      }
      await reloadLocations();
      navigate(`/locations/${saved.location_id}`);
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
      <PageHeader title={isEdit ? 'Edit location' : 'New location'} back />
      <ErrorMessage error={error} />

      <form onSubmit={handleSubmit}>
        <VStack spacing={4} align="stretch" maxW="480px">
          <FormControl isInvalid={!!nameError} isRequired>
            <FormLabel>Name</FormLabel>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Kitchen Pantry"
              autoFocus
            />
            {nameError && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {nameError}
              </Text>
            )}
          </FormControl>

          <FormControl>
            <FormLabel>Description</FormLabel>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional notes about this location"
              rows={3}
            />
          </FormControl>

          <Button type="submit" isLoading={submitting} loadingText="Saving..." width="full">
            {isEdit ? 'Save changes' : 'Create location'}
          </Button>
        </VStack>
      </form>
    </Box>
  );
}
