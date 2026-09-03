/**
 * LocationDetailPage — a location's details and the items stored in it.
 */

import { useEffect, useState, useCallback } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Center,
  HStack,
  IconButton,
  Spinner,
  Text,
  VStack,
  useDisclosure,
} from '@chakra-ui/react';
import {
  getLocation,
  deleteLocation,
  listItems,
} from '@pantry-app/shared';
import { useInventoryContext } from '../contexts/InventoryContext';
import PageHeader from '../components/PageHeader';
import ErrorMessage from '../components/ErrorMessage';
import EmptyState from '../components/EmptyState';
import ItemCard from '../components/ItemCard';
import ConfirmDialog from '../components/ConfirmDialog';
import { PlusIcon, EditIcon, TrashIcon } from '../components/icons';

export default function LocationDetailPage() {
  const { locationId } = useParams();
  const navigate = useNavigate();
  const { reloadLocations } = useInventoryContext();
  const { isOpen, onOpen, onClose } = useDisclosure();

  const [location, setLocation] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [loc, its] = await Promise.all([
        getLocation(locationId),
        listItems({ location_id: locationId }),
      ]);
      setLocation(loc);
      setItems(its);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [locationId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDelete = async () => {
    try {
      setDeleting(true);
      await deleteLocation(locationId);
      await reloadLocations();
      navigate('/locations');
    } catch (err) {
      setError(err);
      setDeleting(false);
      onClose();
    }
  };

  if (loading) {
    return (
      <Center py={12}>
        <Spinner color="brand.500" thickness="3px" />
      </Center>
    );
  }

  if (error && !location) {
    return (
      <Box>
        <PageHeader title="Location" back="/locations" />
        <ErrorMessage error={error} />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title={location.name}
        subtitle={location.description}
        back="/locations"
        actions={
          <HStack>
            <IconButton
              as={RouterLink}
              to={`/locations/${locationId}/edit`}
              aria-label="Edit location"
              icon={<EditIcon boxSize={5} />}
              variant="ghost"
              colorScheme="gray"
            />
            <IconButton
              aria-label="Delete location"
              icon={<TrashIcon boxSize={5} />}
              variant="ghost"
              colorScheme="red"
              onClick={onOpen}
            />
          </HStack>
        }
      />

      <ErrorMessage error={error} />

      <HStack justify="space-between" mb={3}>
        <Text fontWeight="semibold" color="gray.600">
          {items.length} {items.length === 1 ? 'item' : 'items'}
        </Text>
        <Button
          as={RouterLink}
          to={`/items/new?location=${locationId}`}
          size="sm"
          leftIcon={<PlusIcon boxSize={4} />}
        >
          Add item
        </Button>
      </HStack>

      {items.length === 0 ? (
        <EmptyState
          title="No items here yet"
          description="Add the first item stored in this location."
          action={
            <Button as={RouterLink} to={`/items/new?location=${locationId}`} mt={2}>
              Add item
            </Button>
          }
        />
      ) : (
        <VStack spacing={3} align="stretch">
          {items.map((item) => (
            <ItemCard key={item.item_id} item={item} showLocation={false} />
          ))}
        </VStack>
      )}

      <ConfirmDialog
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={handleDelete}
        isLoading={deleting}
        title="Delete location"
        body={`Delete "${location.name}"? Items in it will not be deleted, but will no longer be grouped here.`}
      />
    </Box>
  );
}
