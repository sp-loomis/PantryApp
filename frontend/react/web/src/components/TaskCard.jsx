/**
 * TaskCard
 *
 * One task in a list. A checkbox completes/uncompletes it (for the current
 * window); tapping the name opens the task detail. Shows the recurrence label
 * and an urgency badge.
 */

import { Link as RouterLink } from 'react-router-dom';
import {
  LinkBox,
  LinkOverlay,
  Card,
  CardBody,
  Checkbox,
  Flex,
  Box,
  HStack,
  Heading,
  Text,
  Tag,
  Badge,
} from '@chakra-ui/react';
import { taskStatusBadge, recurrenceLabel } from '../utils/taskStatus';

export default function TaskCard({ task, onToggleComplete, isToggling = false }) {
  const badge = taskStatusBadge(task);
  const recurrence = recurrenceLabel(task);

  return (
    <LinkBox
      as={Card}
      variant="outline"
      opacity={task.done ? 0.6 : 1}
      _hover={{ borderColor: 'brand.300', shadow: 'sm' }}
      transition="all 0.15s"
    >
      <CardBody py={3}>
        <Flex align="flex-start" gap={3}>
          <Checkbox
            isChecked={task.done}
            isDisabled={isToggling}
            onChange={() => onToggleComplete?.(task)}
            colorScheme="brand"
            size="lg"
            mt={0.5}
            // Keep the checkbox from triggering the card's link overlay.
            zIndex={1}
            aria-label={task.done ? `Mark ${task.name} not done` : `Mark ${task.name} done`}
          />

          <Box minW={0} flex="1">
            <LinkOverlay as={RouterLink} to={`/tasks/${task.task_id}`}>
              <Heading
                size="sm"
                noOfLines={1}
                textDecoration={task.done ? 'line-through' : 'none'}
              >
                {task.name}
              </Heading>
            </LinkOverlay>

            <HStack mt={1} spacing={2} color="gray.500" fontSize="sm" flexWrap="wrap">
              <Text>{recurrence}</Text>
              {task.tags?.length > 0 && <Text>·</Text>}
              {task.tags?.map((t) => (
                <Tag key={t} size="sm" colorScheme="brand" variant="subtle">
                  {t}
                </Tag>
              ))}
            </HStack>
          </Box>

          <Badge colorScheme={badge.color} flexShrink={0} borderRadius="md" px={2} py={1}>
            {badge.label}
          </Badge>
        </Flex>
      </CardBody>
    </LinkBox>
  );
}
