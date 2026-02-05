/**
 * ProtectedRoute Component
 * Redirects unauthenticated users to login
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { Box, Spinner, Center } from '@chakra-ui/react';
import { useAuthContext } from '../contexts/AuthContext';

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuthContext();

  if (isLoading) {
    return (
      <Center minH="100vh">
        <Spinner size="xl" />
      </Center>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
