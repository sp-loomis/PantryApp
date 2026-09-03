/**
 * LocationsPage — index of storage locations.
 */

import { Link as RouterLink } from 'react-router-dom';
import {
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
import { useInventoryContext } from '../contexts/InventoryContext';
import PageHeader from '../components/PageHeader';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import { PlusIcon, ChevronRightIcon } from '../components/icons';

export default function LocationsPage() {
  const { locations, locationsLoading, locationsError } = useInventoryContext();

  return (
    <Box>
      <PageHeader
        title="Locations"
        actions={
          <Button as={RouterLink} to="/locations/new" leftIcon={<PlusIcon boxSize={4} />}>
            New
          </Button>
        }
      />

      <ErrorMessage error={locationsError} />

      {locationsLoading ? (
        <Center py={12}>
          <Spinner color="brand.500" thickness="3px" />
        </Center>
      ) : locations.length === 0 ? (
        <EmptyState
          title="No locations yet"
          description="Create a storage location to start organizing your pantry."
          action={
            <Button as={RouterLink} to="/locations/new" mt={2}>
              Create location
            </Button>
          }
        />
      ) : (
        <VStack spacing={3} align="stretch">
          {locations.map((loc) => (
            <LinkBox
              key={loc.location_id}
              as={Card}
              variant="outline"
              _hover={{ borderColor: 'brand.300', shadow: 'sm' }}
              transition="all 0.15s"
            >
              <CardBody>
                <Flex align="center" justify="space-between" gap={3}>
                  <Box minW={0}>
                    <LinkOverlay as={RouterLink} to={`/locations/${loc.location_id}`}>
                      <Heading size="sm" noOfLines={1}>
                        {loc.name}
                      </Heading>
                    </LinkOverlay>
                    {loc.description && (
                      <Text color="gray.500" fontSize="sm" noOfLines={1} mt={0.5}>
                        {loc.description}
                      </Text>
                    )}
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
