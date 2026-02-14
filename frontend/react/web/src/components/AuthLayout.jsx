/**
 * Authentication Layout Component
 *
 * Provides consistent layout for authentication pages.
 * Centers content on desktop, full-width on mobile.
 */

import {
  Box,
  Container,
  Heading,
  Card,
  CardBody,
  VStack
} from '@chakra-ui/react';

export default function AuthLayout({ title, children }) {
  return (
    <Box
      minH="100vh"
      display="flex"
      alignItems="center"
      justifyContent="center"
      bg="gray.50"
      py={8}
    >
      <Container maxW="md">
        <VStack spacing={6}>
          <Heading
            as="h1"
            size="xl"
            textAlign="center"
            color="brand.600"
          >
            {import.meta.env.VITE_APP_NAME || 'Pantry App'}
          </Heading>

          <Card w="full" shadow="md">
            <CardBody>
              <VStack spacing={6} align="stretch">
                <Heading as="h2" size="lg" textAlign="center">
                  {title}
                </Heading>
                {children}
              </VStack>
            </CardBody>
          </Card>
        </VStack>
      </Container>
    </Box>
  );
}
