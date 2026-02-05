/**
 * HomePage Component
 * Protected home page for authenticated users
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Heading,
  Text,
  Button,
  VStack,
  useColorModeValue
} from '@chakra-ui/react';
import { useAuthContext } from '../contexts/AuthContext';

export default function HomePage() {
  const navigate = useNavigate();
  const { user, logout } = useAuthContext();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const bgColor = useColorModeValue('gray.50', 'gray.900');
  const cardBg = useColorModeValue('white', 'gray.800');

  const handleLogout = async () => {
    setIsLoggingOut(true);
    const result = await logout();

    if (result.success) {
      navigate('/login');
    } else {
      setIsLoggingOut(false);
    }
  };

  return (
    <Box minH="100vh" bg={bgColor} py={12}>
      <Container maxW="2xl">
        <Box
          bg={cardBg}
          p={8}
          borderRadius="lg"
          boxShadow="lg"
        >
          <VStack spacing={6} align="stretch">
            <Heading as="h1" size="xl">
              Welcome to Pantry App
            </Heading>

            <Text fontSize="lg">
              You are logged in as: <strong>{user?.email}</strong>
            </Text>

            <Text color="gray.600">
              This is the home page for authenticated users. Inventory management
              features will be added in future releases.
            </Text>

            <Button
              onClick={handleLogout}
              isLoading={isLoggingOut}
              loadingText="Logging out..."
              colorScheme="red"
              variant="outline"
              width="fit-content"
            >
              Log Out
            </Button>
          </VStack>
        </Box>
      </Container>
    </Box>
  );
}
