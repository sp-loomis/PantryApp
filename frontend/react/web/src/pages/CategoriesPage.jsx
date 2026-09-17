/**
 * CategoriesPage — index of item categories.
 *
 * Categories are not held in InventoryContext, so this page loads them directly.
 */

import { useEffect, useState, useCallback } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  Center,
  Flex,
  Heading,
  HStack,
  Spinner,
  Text,
  VStack,
  LinkBox,
  LinkOverlay,
} from '@chakra-ui/react';
import { listCategories } from '@pantry-app/shared';
import PageHeader from '../components/PageHeader';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import { PlusIcon, ChevronRightIcon } from '../components/icons';

export default function CategoriesPage() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setCategories(await listCategories());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Box>
      <PageHeader
        title="Categories"
        actions={
          <Button as={RouterLink} to="/categories/new" leftIcon={<PlusIcon boxSize={4} />}>
            New
          </Button>
        }
      />

      <ErrorMessage error={error} />

      {loading ? (
        <Center py={12}>
          <Spinner color="brand.500" thickness="3px" />
        </Center>
      ) : categories.length === 0 ? (
        <EmptyState
          title="No categories yet"
          description="Group items by a measure (e.g. beef by weight) to see totals and set alerts."
          action={
            <Button as={RouterLink} to="/categories/new" mt={2}>
              Create category
            </Button>
          }
        />
      ) : (
        <VStack spacing={3} align="stretch">
          {categories.map((cat) => (
            <LinkBox
              key={cat.category_id}
              as={Card}
              variant="outline"
              _hover={{ borderColor: 'brand.300', shadow: 'sm' }}
              transition="all 0.15s"
            >
              <CardBody>
                <Flex align="center" justify="space-between" gap={3}>
                  <Box minW={0}>
                    <LinkOverlay as={RouterLink} to={`/categories/${cat.category_id}/edit`}>
                      <Heading size="sm" noOfLines={1}>
                        {cat.name}
                      </Heading>
                    </LinkOverlay>
                    <HStack mt={1} spacing={2}>
                      <Badge colorScheme="brand">{cat.measure_type}</Badge>
                      {cat.preferred_unit && (
                        <Text color="gray.500" fontSize="sm">
                          {cat.preferred_unit}
                        </Text>
                      )}
                    </HStack>
                  </Box>
                  <HStack color="gray.400" flexShrink={0}>
                    <ChevronRightIcon boxSize={5} />
                  </HStack>
                </Flex>
              </CardBody>
            </LinkBox>
          ))}
        </VStack>
      )}
    </Box>
  );
}
