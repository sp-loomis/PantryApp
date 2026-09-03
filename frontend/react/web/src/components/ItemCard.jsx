/**
 * ItemCard
 *
 * Mobile-friendly card for one inventory item in a list. Tapping anywhere opens
 * the item detail. Shows measure, location, tags, and an expiry badge.
 */

import { Link as RouterLink } from 'react-router-dom';
import {
  LinkBox,
  LinkOverlay,
  Card,
  CardBody,
  Flex,
  Box,
  HStack,
  Heading,
  Text,
  Tag,
  Badge,
} from '@chakra-ui/react';
import { formatMeasure } from '@pantry-app/shared';
import { expiryStatus } from '../utils/dates';
import MatchHighlight from './MatchHighlight';

export default function ItemCard({ item, locationName, showLocation = true }) {
  const measure = formatMeasure(item.dimensions);
  const expiry = expiryStatus(item.use_by_date);

  return (
    <LinkBox
      as={Card}
      variant="outline"
      _hover={{ borderColor: 'brand.300', shadow: 'sm' }}
      transition="all 0.15s"
    >
      <CardBody py={3}>
        <Flex justify="space-between" align="flex-start" gap={3}>
          <Box minW={0}>
            <LinkOverlay as={RouterLink} to={`/items/${item.item_id}`}>
              <Heading size="sm" noOfLines={1}>
                {item.match ? (
                  <MatchHighlight text={item.name} spans={item.match.spans} />
                ) : (
                  item.name
                )}
              </Heading>
            </LinkOverlay>

            <HStack mt={1} spacing={2} color="gray.500" fontSize="sm" flexWrap="wrap">
              {measure && <Text>{measure}</Text>}
              {measure && showLocation && locationName && <Text>·</Text>}
              {showLocation && locationName && <Text noOfLines={1}>{locationName}</Text>}
            </HStack>

            {item.tags?.length > 0 && (
              <HStack mt={2} spacing={1} flexWrap="wrap">
                {item.tags.map((t) => (
                  <Tag key={t} size="sm" colorScheme="brand" variant="subtle">
                    {t}
                  </Tag>
                ))}
              </HStack>
            )}
          </Box>

          {expiry && (
            <Badge colorScheme={expiry.color} flexShrink={0} borderRadius="md" px={2} py={1}>
              {expiry.label}
            </Badge>
          )}
        </Flex>
      </CardBody>
    </LinkBox>
  );
}
