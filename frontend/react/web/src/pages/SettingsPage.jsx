/**
 * SettingsPage — hub for account/app settings.
 *
 * Currently a single card linking to Integrations (Slack). Kept as its own page
 * so future settings groups slot in beside it.
 */

import { Link as RouterLink } from 'react-router-dom';
import { Box, Flex, Heading, Text, VStack } from '@chakra-ui/react';
import { SlackIcon, ChevronRightIcon } from '../components/icons';

const SETTINGS_ITEMS = [
  {
    to: '/settings/integrations',
    icon: SlackIcon,
    title: 'Integrations',
    description: 'Connect Slack to receive reports and notifications.',
  },
];

export default function SettingsPage() {
  return (
    <Box>
      <Text fontSize="2xl" fontWeight="bold" mb={4}>
        Settings
      </Text>

      <VStack spacing={3} align="stretch">
        {SETTINGS_ITEMS.map((item) => {
          const IconCmp = item.icon;
          return (
            <Flex
              key={item.to}
              as={RouterLink}
              to={item.to}
              align="center"
              gap={4}
              bg="white"
              borderWidth="1px"
              borderColor="gray.200"
              borderRadius="lg"
              boxShadow="sm"
              p={4}
              _hover={{ borderColor: 'brand.300', boxShadow: 'md' }}
            >
              <IconCmp boxSize={6} color="brand.500" />
              <Box flex="1" minW={0}>
                <Heading size="sm">{item.title}</Heading>
                <Text fontSize="sm" color="gray.500">
                  {item.description}
                </Text>
              </Box>
              <ChevronRightIcon boxSize={5} color="gray.400" />
            </Flex>
          );
        })}
      </VStack>
    </Box>
  );
}
