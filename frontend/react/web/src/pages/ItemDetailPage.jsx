/**
 * ItemDetailPage — full detail for one item, with edit/delete.
 */

import { useEffect, useState, useCallback } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardBody,
  Center,
  Divider,
  Flex,
  HStack,
  IconButton,
  Link,
  Spinner,
  Tag,
  Text,
  VStack,
  Wrap,
  WrapItem,
  Badge,
  useDisclosure,
} from '@chakra-ui/react';
import { getItem, deleteItem, formatMeasure } from '@pantry-app/shared';
import { useInventoryContext } from '../contexts/InventoryContext';
import PageHeader from '../components/PageHeader';
import ErrorMessage from '../components/ErrorMessage';
import ConfirmDialog from '../components/ConfirmDialog';
import { EditIcon, TrashIcon } from '../components/icons';
import { formatDate, expiryStatus } from '../utils/dates';

function Field({ label, children }) {
  return (
    <Box>
      <Text fontSize="xs" textTransform="uppercase" color="gray.400" fontWeight="semibold" mb={1}>
        {label}
      </Text>
      {children}
    </Box>
  );
}

export default function ItemDetailPage() {
  const { itemId } = useParams();
  const navigate = useNavigate();
  const { locationName } = useInventoryContext();
  const { isOpen, onOpen, onClose } = useDisclosure();

  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setItem(await getItem(itemId));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [itemId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDelete = async () => {
    try {
      setDeleting(true);
      await deleteItem(itemId);
      navigate(-1);
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

  if (error && !item) {
    return (
      <Box>
        <PageHeader title="Item" back />
        <ErrorMessage error={error} />
      </Box>
    );
  }

  const measure = formatMeasure(item.dimensions);
  const expiry = expiryStatus(item.use_by_date);

  return (
    <Box>
      <PageHeader
        title={item.name}
        back
        actions={
          <HStack>
            <IconButton
              as={RouterLink}
              to={`/items/${itemId}/edit`}
              aria-label="Edit item"
              icon={<EditIcon boxSize={5} />}
              variant="ghost"
              colorScheme="gray"
            />
            <IconButton
              aria-label="Delete item"
              icon={<TrashIcon boxSize={5} />}
              variant="ghost"
              colorScheme="red"
              onClick={onOpen}
            />
          </HStack>
        }
      />

      <ErrorMessage error={error} />

      <Card variant="outline">
        <CardBody>
          <VStack align="stretch" spacing={4}>
            <Field label="Location">
              <Link
                as={RouterLink}
                to={`/locations/${item.location_id}`}
                color="brand.600"
                fontWeight="medium"
              >
                {locationName(item.location_id)}
              </Link>
            </Field>

            <Field label="Measure">
              <Text>{measure || '—'}</Text>
            </Field>

            <Field label="Use-by date">
              {item.use_by_date ? (
                <Flex align="center" gap={2}>
                  <Text>{formatDate(item.use_by_date)}</Text>
                  {expiry && <Badge colorScheme={expiry.color}>{expiry.label}</Badge>}
                </Flex>
              ) : (
                <Text>—</Text>
              )}
            </Field>

            <Field label="Tags">
              {item.tags?.length > 0 ? (
                <Wrap spacing={2}>
                  {item.tags.map((tag) => (
                    <WrapItem key={tag}>
                      <Link as={RouterLink} to={`/tags/${encodeURIComponent(tag)}`}>
                        <Tag colorScheme="brand" variant="subtle">
                          {tag}
                        </Tag>
                      </Link>
                    </WrapItem>
                  ))}
                </Wrap>
              ) : (
                <Text>—</Text>
              )}
            </Field>

            {item.notes && (
              <>
                <Divider />
                <Field label="Notes">
                  <Text whiteSpace="pre-wrap">{item.notes}</Text>
                </Field>
              </>
            )}
          </VStack>
        </CardBody>
      </Card>

      <Button as={RouterLink} to={`/items/${itemId}/edit`} mt={4} width={{ base: 'full', md: 'auto' }}>
        Edit item
      </Button>

      <ConfirmDialog
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={handleDelete}
        isLoading={deleting}
        title="Delete item"
        body={`Delete "${item.name}"? This cannot be undone.`}
      />
    </Box>
  );
}
