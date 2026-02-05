/**
 * AuthContext
 * Provides authentication state to the application
 */

import React, { createContext, useContext } from 'react';
import { useAuth } from '@pantry-app/shared';

const AuthContext = createContext(null);

/**
 * AuthProvider component
 * Wraps the app and provides auth state
 */
export function AuthProvider({ children }) {
  const auth = useAuth();

  return (
    <AuthContext.Provider value={auth}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * useAuthContext hook
 * Access auth state from any component
 */
export function useAuthContext() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuthContext must be used within AuthProvider');
  }

  return context;
}
