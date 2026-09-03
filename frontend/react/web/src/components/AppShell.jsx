/**
 * AppShell
 *
 * Mobile-first responsive navigation shell for the authenticated app.
 *   - mobile (base): a thumb-reachable fixed bottom tab bar
 *   - desktop (lg+): a left sidebar
 * One component, driven by Chakra responsive props. Content renders via <Outlet/>.
 *
 * Tabs: Search · Locations · Tags · [+ Add]
 */

import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Box, Flex, HStack, VStack, Text, Heading } from '@chakra-ui/react';
import { SearchIcon, LocationIcon, TagIcon, PlusIcon } from './icons';

const NAV_ITEMS = [
  { to: '/', label: 'Search', icon: SearchIcon, end: true },
  { to: '/locations', label: 'Locations', icon: LocationIcon },
  { to: '/tags', label: 'Tags', icon: TagIcon },
  { to: '/items/new', label: 'Add', icon: PlusIcon, accent: true },
];

const APP_NAME = import.meta.env.VITE_APP_NAME || 'Pantry App';

/** True when the current path should mark a nav item active. */
function useIsActive() {
  const { pathname } = useLocation();
  return (item) => {
    if (item.end) return pathname === '/';
    return pathname === item.to || pathname.startsWith(`${item.to}/`);
  };
}

function SidebarLink({ item, active }) {
  const IconCmp = item.icon;
  return (
    <NavLink to={item.to} style={{ width: '100%' }}>
      <HStack
        spacing={3}
        px={4}
        py={3}
        borderRadius="lg"
        color={active ? 'brand.600' : 'gray.600'}
        bg={active ? 'brand.50' : 'transparent'}
        fontWeight={active ? 'semibold' : 'medium'}
        _hover={{ bg: active ? 'brand.50' : 'gray.100' }}
      >
        <IconCmp boxSize={5} />
        <Text>{item.label}</Text>
      </HStack>
    </NavLink>
  );
}

function BottomTab({ item, active }) {
  const IconCmp = item.icon;
  // The Add tab is visually accented as the primary action.
  if (item.accent) {
    return (
      <NavLink to={item.to} aria-label={item.label}>
        <VStack spacing={0} justify="center" minW="56px" minH="56px">
          <Flex
            align="center"
            justify="center"
            boxSize="44px"
            borderRadius="full"
            bg="brand.500"
            color="white"
            boxShadow="md"
          >
            <IconCmp boxSize={6} />
          </Flex>
        </VStack>
      </NavLink>
    );
  }
  return (
    <NavLink to={item.to} aria-label={item.label}>
      <VStack
        spacing={0.5}
        justify="center"
        minW="56px"
        minH="56px"
        color={active ? 'brand.600' : 'gray.500'}
      >
        <IconCmp boxSize={5} />
        <Text fontSize="xs" fontWeight={active ? 'semibold' : 'medium'}>
          {item.label}
        </Text>
      </VStack>
    </NavLink>
  );
}

export default function AppShell() {
  const isActive = useIsActive();

  return (
    <Flex minH="100vh" bg="gray.50">
      {/* Desktop sidebar */}
      <Box
        as="nav"
        display={{ base: 'none', lg: 'flex' }}
        flexDirection="column"
        w="240px"
        flexShrink={0}
        bg="white"
        borderRight="1px solid"
        borderColor="gray.200"
        px={3}
        py={6}
        position="sticky"
        top={0}
        h="100vh"
      >
        <Heading size="md" color="brand.600" px={4} mb={6}>
          {APP_NAME}
        </Heading>
        <VStack spacing={1} align="stretch">
          {NAV_ITEMS.map((item) => (
            <SidebarLink key={item.to} item={item} active={isActive(item)} />
          ))}
        </VStack>
      </Box>

      {/* Content */}
      <Box
        flex="1"
        minW={0}
        px={{ base: 4, md: 8 }}
        py={{ base: 4, md: 8 }}
        pb={{ base: '88px', lg: 8 }} // clear the fixed bottom bar on mobile
        maxW="960px"
        w="full"
        mx="auto"
      >
        <Outlet />
      </Box>

      {/* Mobile bottom tab bar */}
      <HStack
        as="nav"
        display={{ base: 'flex', lg: 'none' }}
        position="fixed"
        bottom={0}
        left={0}
        right={0}
        justify="space-around"
        align="center"
        bg="white"
        borderTop="1px solid"
        borderColor="gray.200"
        px={2}
        py={1}
        zIndex={10}
        boxShadow="0 -1px 6px rgba(0,0,0,0.04)"
      >
        {NAV_ITEMS.map((item) => (
          <BottomTab key={item.to} item={item} active={isActive(item)} />
        ))}
      </HStack>
    </Flex>
  );
}
