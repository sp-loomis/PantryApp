/**
 * Home Page (Protected)
 *
 * Landing page for authenticated users.
 */

import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Heading,
  Text,
  Button,
  VStack,
  Card,
  CardBody
} from '@chakra-ui/react';
import { useAuthContext } from '../contexts/AuthContext';

export default function HomePage() {
  const navigate = useNavigate();
  const { user, logout } = useAuthContext();

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  return (
    <Box minH="100vh" bg="gray.50" py={8}>
      <Container maxW="container.md">
        <VStack spacing={6} align="stretch">
          <Heading as="h1" size="xl" color="brand.600">
            {import.meta.env.VITE_APP_NAME || 'Pantry App'}
          </Heading>

          <Card>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <Heading as="h2" size="lg">
                  Welcome! 👋
                </Heading>

                <Text fontSize="lg">
                  You are logged in as: <strong>{user?.email}</strong>
                </Text>

                <Text color="gray.600">
                  This is the home page of Pantry App. Authentication is working!
                </Text>

                <Text color="gray.600" fontSize="sm">
                  Future features like inventory management will be added here.
                </Text>

                <Button
                  colorScheme="red"
                  variant="outline"
                  onClick={handleLogout}
                  width={{ base: 'full', md: 'auto' }}
                >
                  Sign Out
                </Button>
              </VStack>
            </CardBody>
          </Card>
        </VStack>
      </Container>
    </Box>
  );
}
