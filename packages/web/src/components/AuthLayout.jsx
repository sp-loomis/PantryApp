/**
 * AuthLayout Component
 * Consistent layout for authentication pages
 */

import React from 'react';
import {
  Box,
  Container,
  Heading,
  VStack,
  useColorModeValue
} from '@chakra-ui/react';

export default function AuthLayout({ title, children }) {
  const bgColor = useColorModeValue('gray.50', 'gray.900');
  const cardBg = useColorModeValue('white', 'gray.800');

  return (
    <Box minH="100vh" bg={bgColor} py={12}>
      <Container maxW="md">
        <Box
          bg={cardBg}
          p={8}
          borderRadius="lg"
          boxShadow="lg"
        >
          <VStack spacing={6} align="stretch">
            <Heading as="h1" size="lg" textAlign="center">
              {title}
            </Heading>
            {children}
          </VStack>
        </Box>
      </Container>
    </Box>
  );
}
