/**
 * EmptyState
 *
 * Friendly placeholder for empty lists, with an optional call-to-action.
 */

import { VStack, Text } from '@chakra-ui/react';

export default function EmptyState({ title, description, action }) {
  return (
    <VStack py={12} spacing={3} textAlign="center" color="gray.500">
      <Text fontSize="lg" fontWeight="medium" color="gray.600">
        {title}
      </Text>
      {description && <Text fontSize="sm">{description}</Text>}
      {action}
    </VStack>
  );
}
