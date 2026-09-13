/**
 * NotificationsMenu — the toolbar bell + unread dropdown.
 *
 * Shows a bell with an unread-count badge, available app-wide via the AppShell.
 * Opening it lists recent unread messages; each links to the message in the log
 * via `/messages#<message_id>` (the log then scrolls to and marks it read).
 * Refreshes on open and whenever the route changes so the badge stays current.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  Badge,
  Box,
  Divider,
  Link,
  Popover,
  PopoverArrow,
  PopoverBody,
  PopoverContent,
  PopoverHeader,
  PopoverTrigger,
  Text,
  VStack,
} from '@chakra-ui/react';
import { listUnread } from '@pantry-app/shared';
import { BellIcon } from './icons';

const MAX_PREVIEW = 5;

export default function NotificationsMenu() {
  const location = useLocation();
  const [unread, setUnread] = useState({ messages: [], unread_count: 0 });

  const refresh = useCallback(async () => {
    try {
      setUnread(await listUnread());
    } catch {
      // Non-fatal for the toolbar; leave the last known state.
    }
  }, []);

  // Refresh on mount and whenever the route changes (e.g. after reading one).
  useEffect(() => {
    refresh();
  }, [refresh, location.pathname, location.hash]);

  const count = unread.unread_count || 0;
  const preview = (unread.messages || []).slice(0, MAX_PREVIEW);

  return (
    <Popover placement="bottom-end" onOpen={refresh}>
      <PopoverTrigger>
        <Box as="button" position="relative" p={2} aria-label="Notifications">
          <BellIcon boxSize={5} color="gray.600" />
          {count > 0 && (
            <Badge
              colorScheme="red"
              borderRadius="full"
              position="absolute"
              top="0"
              right="0"
              fontSize="0.6rem"
              px={1.5}
            >
              {count > 9 ? '9+' : count}
            </Badge>
          )}
        </Box>
      </PopoverTrigger>
      <PopoverContent w="320px">
        <PopoverArrow />
        <PopoverHeader fontWeight="semibold" fontSize="sm">
          Notifications {count > 0 && `(${count} unread)`}
        </PopoverHeader>
        <PopoverBody px={0}>
          {preview.length === 0 ? (
            <Text px={4} py={2} fontSize="sm" color="gray.500">
              You&apos;re all caught up.
            </Text>
          ) : (
            <VStack spacing={0} align="stretch">
              {preview.map((message) => (
                <Link
                  key={message.message_id}
                  as={RouterLink}
                  to={`/messages#${message.message_id}`}
                  px={4}
                  py={2}
                  _hover={{ bg: 'gray.50' }}
                >
                  <Text fontSize="sm" fontWeight="medium" noOfLines={1}>
                    {message.title}
                  </Text>
                </Link>
              ))}
            </VStack>
          )}
          <Divider my={1} />
          <Link
            as={RouterLink}
            to="/messages"
            display="block"
            px={4}
            py={2}
            fontSize="sm"
            color="brand.600"
            fontWeight="medium"
          >
            See all messages
          </Link>
        </PopoverBody>
      </PopoverContent>
    </Popover>
  );
}
