/**
 * AppShell
 *
 * Mobile-first responsive navigation shell for the authenticated app.
 *   - mobile (base): a thumb-reachable fixed bottom tab bar
 *   - desktop (lg+): a left sidebar
 * One component, driven by Chakra responsive props. Content renders via <Outlet/>.
 *
 * Nav model:
 *   - Desktop sidebar shows every destination (NAV_ITEMS).
 *   - Mobile keeps only the primary destinations as tabs (PRIMARY_ITEMS) plus a
 *     "More" tab that opens a bottom sheet with the secondary ones (MORE_ITEMS).
 *     Bottom bar caps at 5 targets so tap targets stay full-size on a phone.
 *
 * Mobile bar: Search · Locations · Tasks · [+ Add] · More
 * More sheet: Categories · Reports · Tags · Settings
 */

import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Box,
  Flex,
  HStack,
  VStack,
  Text,
  Heading,
  IconButton,
  Drawer,
  DrawerOverlay,
  DrawerContent,
  DrawerHeader,
  DrawerBody,
  useDisclosure,
} from '@chakra-ui/react';
import {
  SearchIcon,
  LocationIcon,
  CategoryIcon,
  TaskIcon,
  TagIcon,
  PlusIcon,
  ReportIcon,
  SettingsIcon,
  LogoutIcon,
  MoreIcon,
} from './icons';
import NotificationsMenu from './NotificationsMenu';
import { useAuthContext } from '../contexts/AuthContext';

const NAV_ITEMS = [
  { to: '/', label: 'Search', icon: SearchIcon, end: true },
  { to: '/locations', label: 'Locations', icon: LocationIcon },
  { to: '/categories', label: 'Categories', icon: CategoryIcon },
  { to: '/tasks', label: 'Tasks', icon: TaskIcon },
  { to: '/reports', label: 'Reports', icon: ReportIcon },
  { to: '/tags', label: 'Tags', icon: TagIcon },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
  { to: '/items/new', label: 'Add', icon: PlusIcon, accent: true },
];

// Mobile bottom bar: primary destinations only. Add is accented as the primary
// action. Order here is the on-screen order (More is appended in render).
const PRIMARY_TABS = ['/', '/locations', '/tasks', '/items/new'];
const PRIMARY_ITEMS = PRIMARY_TABS.map((to) => NAV_ITEMS.find((i) => i.to === to));
// Everything else lives behind the "More" tab's bottom sheet.
const MORE_ITEMS = NAV_ITEMS.filter((i) => !PRIMARY_TABS.includes(i.to));

const APP_NAME = import.meta.env.VITE_APP_NAME || 'Homestead Manager';

/** True when the current path should mark a nav item active. */
function useIsActive() {
  const { pathname } = useLocation();
  return (item) => {
    if (item.end) return pathname === '/';
    return pathname === item.to || pathname.startsWith(`${item.to}/`);
  };
}

function SidebarLink({ item, active, onClick }) {
  const IconCmp = item.icon;
  return (
    <NavLink to={item.to} style={{ width: '100%' }} onClick={onClick}>
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
  // The Add tab is visually accented as the primary action (add-circle icon in
  // brand color, sized up so it stands out among the tabs).
  if (item.accent) {
    return (
      <NavLink to={item.to} aria-label={item.label}>
        <VStack spacing={0} justify="center" minW="56px" minH="56px" color="brand.500">
          <IconCmp boxSize={9} />
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

/** The "More" bottom tab: a button (not a link) that opens the overflow sheet. */
function MoreTab({ active, onClick }) {
  return (
    <Box
      as="button"
      type="button"
      onClick={onClick}
      aria-label="More"
      aria-haspopup="dialog"
    >
      <VStack
        spacing={0.5}
        justify="center"
        minW="56px"
        minH="56px"
        color={active ? 'brand.600' : 'gray.500'}
      >
        <MoreIcon boxSize={5} />
        <Text fontSize="xs" fontWeight={active ? 'semibold' : 'medium'}>
          More
        </Text>
      </VStack>
    </Box>
  );
}

export default function AppShell() {
  const isActive = useIsActive();
  const navigate = useNavigate();
  const { logout } = useAuthContext();
  const { isOpen, onOpen, onClose } = useDisclosure();

  const handleSignOut = async () => {
    await logout();
    navigate('/login');
  };

  // "More" tab reads as active when any of its hidden destinations is current.
  const moreActive = MORE_ITEMS.some((item) => isActive(item));

  return (
    <Flex minH="100vh" bg="gray.50">
      {/* Desktop sidebar — shows every destination. */}
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
        {/* Top toolbar: notifications bell, reachable from anywhere in the app. */}
        <Flex justify="flex-end" align="center" gap={1} mb={{ base: 2, md: 4 }}>
          <NotificationsMenu />
          <IconButton
            aria-label="Sign out"
            icon={<LogoutIcon boxSize={5} />}
            variant="ghost"
            color="gray.600"
            onClick={handleSignOut}
          />
        </Flex>
        <Outlet />
      </Box>

      {/* Mobile bottom tab bar — primary destinations + More. */}
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
        {PRIMARY_ITEMS.map((item) => (
          <BottomTab key={item.to} item={item} active={isActive(item)} />
        ))}
        <MoreTab active={moreActive} onClick={onOpen} />
      </HStack>

      {/* Mobile "More" overflow sheet — secondary destinations. */}
      <Drawer
        isOpen={isOpen}
        onClose={onClose}
        placement="bottom"
        // Bottom sheet is a mobile-only affordance; harmless if lg is never open.
      >
        <DrawerOverlay />
        <DrawerContent borderTopRadius="xl" pb="env(safe-area-inset-bottom)">
          <DrawerHeader pb={2}>More</DrawerHeader>
          <DrawerBody pb={4}>
            <VStack spacing={1} align="stretch">
              {MORE_ITEMS.map((item) => (
                <SidebarLink
                  key={item.to}
                  item={item}
                  active={isActive(item)}
                  onClick={onClose}
                />
              ))}
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </Flex>
  );
}
