/**
 * ItemDetailPage — full detail for one item, with edit / use (consume) / delete.
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
  FormControl,
  FormLabel,
  HStack,
  IconButton,
  Link,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  NumberInput,
  NumberInputField,
  Select,
  Spinner,
  Tag,
  Text,
  VStack,
  Wrap,
  WrapItem,
  Badge,
  useDisclosure,
  useToast,
} from '@chakra-ui/react';
import { getItem, deleteItem, consumeItem, formatMeasure } from '@pantry-app/shared';
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
  const toast = useToast();
  const { locationName } = useInventoryContext();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const consume = useDisclosure();

  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Consume-dialog state.
  const [consumeType, setConsumeType] = useState('');
  const [consumeValue, setConsumeValue] = useState('');
  const [consuming, setConsuming] = useState(false);
  const [consumeError, setConsumeError] = useState(null);

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

  const openConsume = () => {
    setConsumeError(null);
    setConsumeValue('');
    setConsumeType(item.dimensions?.[0]?.dimension_type ?? '');
    consume.onOpen();
  };

  // amount === null consumes the whole item (deplete).
  const runConsume = async (amount) => {
    try {
      setConsuming(true);
      setConsumeError(null);
      const res = await consumeItem(itemId, amount);
      consume.onClose();
      if (res.depleted) {
        toast({ title: `Used up "${item.name}"`, status: 'success', duration: 3000 });
        navigate(-1);
      } else {
        setItem(res.item);
        toast({ title: 'Recorded usage', status: 'success', duration: 2000 });
      }
    } catch (err) {
      setConsumeError(err);
    } finally {
      setConsuming(false);
    }
  };

  const submitConsumeAmount = () => {
    const unit = item.dimensions?.find((d) => d.dimension_type === consumeType)?.unit;
    const value = Number(consumeValue);
    if (!consumeType || !unit || !Number.isFinite(value) || value <= 0) {
      setConsumeError(new Error('Enter an amount greater than zero.'));
      return;
    }
    runConsume({ dimension_type: consumeType, value, unit });
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
  const hasDimensions = (item.dimensions?.length ?? 0) > 0;

  return (
    <Box>
      <PageHeader
        title={item.name}
        back
        actions={
          <HStack>
            <Button size="sm" colorScheme="brand" variant="outline" onClick={openConsume}>
              Use
            </Button>
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

      <HStack mt={4} spacing={3}>
        <Button onClick={openConsume} width={{ base: 'full', md: 'auto' }}>
          Use
        </Button>
        <Button
          as={RouterLink}
          to={`/items/${itemId}/edit`}
          variant="outline"
          width={{ base: 'full', md: 'auto' }}
        >
          Edit item
        </Button>
      </HStack>

      <ConfirmDialog
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={handleDelete}
        isLoading={deleting}
        title="Delete item"
        body={`Delete "${item.name}"? This removes it from your inventory (it isn't counted as usage).`}
      />

      {/* Consume (record usage) dialog — distinct from delete. */}
      <Modal isOpen={consume.isOpen} onClose={consume.onClose} isCentered>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Use “{item.name}”</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack align="stretch" spacing={4}>
              <ErrorMessage error={consumeError} />
              {hasDimensions ? (
                <>
                  <Text fontSize="sm" color="gray.500">
                    Record how much you used. Using the last of it marks the item depleted.
                  </Text>
                  {item.dimensions.length > 1 && (
                    <FormControl>
                      <FormLabel>Measure</FormLabel>
                      <Select
                        value={consumeType}
                        onChange={(e) => setConsumeType(e.target.value)}
                      >
                        {item.dimensions.map((d) => (
                          <option key={d.dimension_type} value={d.dimension_type}>
                            {d.dimension_type} ({d.unit})
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                  )}
                  <FormControl>
                    <FormLabel>
                      Amount used
                      {consumeType
                        ? ` (${item.dimensions.find((d) => d.dimension_type === consumeType)?.unit})`
                        : ''}
                    </FormLabel>
                    <NumberInput min={0} value={consumeValue} onChange={(v) => setConsumeValue(v)}>
                      <NumberInputField placeholder="0" />
                    </NumberInput>
                  </FormControl>
                </>
              ) : (
                <Text fontSize="sm" color="gray.500">
                  This item has no measured quantity — using it marks it depleted.
                </Text>
              )}
            </VStack>
          </ModalBody>
          <ModalFooter gap={3}>
            {hasDimensions && (
              <Button
                colorScheme="brand"
                onClick={submitConsumeAmount}
                isLoading={consuming}
              >
                Use amount
              </Button>
            )}
            <Button
              variant={hasDimensions ? 'outline' : 'solid'}
              colorScheme="brand"
              onClick={() => runConsume(null)}
              isLoading={consuming}
            >
              Use all
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
}
